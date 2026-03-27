import os
from pathlib import Path
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.core.exceptions import (
    NoVideoGeneratedError,
    VertexAPIError,
    VertexSafetyError,
    VertexTimeoutError,
)
from app.core.logger import get_logger
from app.schemas.video_schema import (
    GenerationTask,
    ModelsListResponse,
    TASK_DESCRIPTIONS,
    VideoGenerationRequest,
    VideoGenerationResponse,
)
from app.services import vertex_service
from app.services import history_service

router = APIRouter()
logger = get_logger(__name__)


_EXPORTS_DIR = Path(__file__).resolve().parents[2] / "exports"


class HistoryEntryRequest(BaseModel):
    filename: str
    prompt: str | None = None
    model: str | None = None
    task: str | None = None
    duration: int | None = None
    aspect_ratio: str | None = None


@router.post(
    "/history",
    summary="Save a history entry for a completed generation",
)
def post_history(entry: HistoryEntryRequest) -> dict:
    saved = history_service.save_entry(
        filename=entry.filename,
        prompt=entry.prompt,
        model=entry.model,
        task=entry.task,
        duration=entry.duration,
        aspect_ratio=entry.aspect_ratio,
    )
    return saved


@router.get(
    "/history",
    summary="List previously generated videos",
)
def get_history() -> dict:
    return {"items": history_service.list_entries()}


@router.get(
    "/tasks",
    summary="List available generation task types",
)
def get_tasks() -> dict:
    return {
        "tasks": [
            {"task": t.value, "description": TASK_DESCRIPTIONS[t]}
            for t in GenerationTask
        ]
    }


@router.get(
    "/estimate",
    summary="Estimate generation cost for given parameters",
)
def get_estimate(
    model: str = Query(default=vertex_service.DEFAULT_MODEL),
    duration: int = Query(default=5, ge=1, le=60),
    sample_count: int = Query(default=1, ge=1, le=4),
    generate_audio: bool = Query(default=False),
) -> dict:
    return vertex_service.estimate_cost(model, duration, sample_count, generate_audio)


@router.get(
    "/models",
    response_model=ModelsListResponse,
    summary="List supported Veo models with current-location metadata",
)
def get_models() -> ModelsListResponse:
    models = vertex_service.list_models(check_live=False)
    return ModelsListResponse(
        current_location=settings.gcp_location,
        default_model=vertex_service.DEFAULT_MODEL,
        models=models,
    )


@router.get(
    "/models/check",
    response_model=ModelsListResponse,
    summary="Probe each model endpoint at the configured location (live check)",
)
def check_models() -> ModelsListResponse:
    try:
        models = vertex_service.list_models(check_live=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ModelsListResponse(
        current_location=settings.gcp_location,
        default_model=vertex_service.DEFAULT_MODEL,
        models=models,
    )


@router.post(
    "/generate-one",
    response_model=VideoGenerationResponse,
    summary="Generate a video — task type determines required inputs",
)
def generate_one(request: VideoGenerationRequest) -> VideoGenerationResponse:
    logger.info(
        "POST /generate-one  task=%s  model=%s  prompt=%.80s  duration=%ds",
        request.task,
        request.model,
        request.prompt,
        request.duration,
    )

    try:
        output_path = vertex_service.generate_video(
            task=request.task,
            prompt=request.prompt,
            duration=request.duration,
            model=request.model,
            config=request.config,
            image_gcs_uri=request.image_gcs_uri,
            subject_description=request.subject_description,
            video_gcs_uri=request.video_gcs_uri,
            mask_gcs_uri=request.mask_gcs_uri,
        )
    except VertexTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except VertexSafetyError as exc:
        raise HTTPException(status_code=400, detail=f"Safety filter rejection: {exc}") from exc
    except (VertexAPIError, NoVideoGeneratedError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return VideoGenerationResponse(
        status="success",
        file_path=str(output_path),
        message="Video generated successfully",
        model=request.model,
    )

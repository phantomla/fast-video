from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.vertex_service import DEFAULT_MODEL, SUPPORTED_MODELS

AspectRatio = Literal["16:9", "9:16", "1:1"]


class GenerationTask(str, Enum):
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"
    REFERENCE_SUBJECT = "reference_subject"
    REFERENCE_STYLE = "reference_style"
    VIDEO_EXTENSION = "video_extension"
    INPAINT_INSERT = "inpaint_insert"
    INPAINT_REMOVE = "inpaint_remove"


TASK_DESCRIPTIONS: dict[str, str] = {
    GenerationTask.TEXT_TO_VIDEO: "Generate video from a text prompt only.",
    GenerationTask.IMAGE_TO_VIDEO: "Animate a starting image with an optional text prompt.",
    GenerationTask.REFERENCE_SUBJECT: "Generate video keeping a subject consistent with reference images.",
    GenerationTask.REFERENCE_STYLE: "Generate video in the visual style of reference images.",
    GenerationTask.VIDEO_EXTENSION: "Extend an existing video with new content.",
    GenerationTask.INPAINT_INSERT: "Insert new content into a masked region of a video.",
    GenerationTask.INPAINT_REMOVE: "Remove content from a masked region of a video.",
}


class VideoGenerationConfig(BaseModel):
    """Fine-grained Veo generation parameters (all optional)."""

    aspect_ratio: AspectRatio = Field(
        default="16:9",
        description="Output video aspect ratio. One of: 16:9, 9:16, 1:1",
    )
    sample_count: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of video samples to generate (1–4)",
    )
    resolution: str | None = Field(
        default=None,
        description="Output video resolution, e.g. '720p' or '1080p'",
    )
    seed: int | None = Field(
        default=None,
        ge=0,
        description="Random seed for reproducible generation",
    )
    storage_uri: str | None = Field(
        default=None,
        description="GCS URI prefix where generated videos should be saved by Vertex AI (e.g. gs://bucket/output/)",
    )
    generate_audio: bool = Field(
        default=False,
        description="Generate audio alongside the video (Veo 3.0+ only)",
    )


class VideoGenerationRequest(BaseModel):
    task: GenerationTask = Field(
        default=GenerationTask.TEXT_TO_VIDEO,
        description="Generation task type. Determines what inputs are required.",
    )
    prompt: str = Field(..., min_length=1, max_length=2000, description="Text prompt for video generation")
    duration: int = Field(..., ge=4, le=8, description="Video duration in seconds. Supported values depend on task: [4, 6, 8]")
    model: str = Field(
        default=DEFAULT_MODEL,
        description=f"Veo model ID. Available: {list(SUPPORTED_MODELS)}",
    )
    config: VideoGenerationConfig = Field(
        default_factory=VideoGenerationConfig,
        description="Advanced generation configuration parameters",
    )

    # ── Task-specific inputs ──────────────────────────────────────────────────

    # image_to_video / reference_subject / reference_style
    image_gcs_uri: str | None = Field(
        default=None,
        description="GCS URI of input image for image_to_video (e.g. gs://bucket/frame.jpg)",
    )

    # reference_subject: subject description for the reference images
    subject_description: str | None = Field(
        default=None,
        max_length=500,
        description="Short description of the subject in the reference image (reference_subject task)",
    )

    # video_extension / inpaint_insert / inpaint_remove
    video_gcs_uri: str | None = Field(
        default=None,
        description="GCS URI of the input video (video_extension / inpaint tasks)",
    )

    # inpaint_insert / inpaint_remove
    mask_gcs_uri: str | None = Field(
        default=None,
        description="GCS URI of the mask video/image (inpaint tasks)",
    )

    @model_validator(mode="after")
    def _check_required_inputs(self) -> "VideoGenerationRequest":
        task = self.task
        if task == GenerationTask.IMAGE_TO_VIDEO and not self.image_gcs_uri:
            raise ValueError("image_gcs_uri is required for image_to_video task")
        if task in (GenerationTask.REFERENCE_SUBJECT, GenerationTask.REFERENCE_STYLE) and not self.image_gcs_uri:
            raise ValueError("image_gcs_uri is required for reference tasks")
        if task == GenerationTask.VIDEO_EXTENSION and not self.video_gcs_uri:
            raise ValueError("video_gcs_uri is required for video_extension task")
        if task in (GenerationTask.INPAINT_INSERT, GenerationTask.INPAINT_REMOVE):
            if not self.video_gcs_uri:
                raise ValueError("video_gcs_uri is required for inpaint tasks")
            if not self.mask_gcs_uri:
                raise ValueError("mask_gcs_uri is required for inpaint tasks")
        return self


class VideoGenerationResponse(BaseModel):
    status: str
    file_path: str
    message: str
    model: str


class ModelInfo(BaseModel):
    model_id: str
    display_name: str
    description: str
    supported_locations: list[str]
    active_at_current_location: bool
    supports_audio: bool
    price_per_second_usd: float
    live_status: str | None = None


class ModelsListResponse(BaseModel):
    current_location: str
    default_model: str
    models: list[ModelInfo]

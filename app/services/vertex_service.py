import base64
import time
from pathlib import Path
from typing import Any

import google.auth.transport.requests
import requests
from google.oauth2 import service_account

from app.core.config import settings
from app.core.exceptions import (
    NoVideoGeneratedError,
    VertexAPIError,
    VertexSafetyError,
    VertexTimeoutError,
)
from app.core.logger import get_logger
from app.utils.file_utils import build_output_path

logger = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_POLL_INTERVAL_S = 10
_MAX_WAIT_S = 360

DEFAULT_MODEL = "veo-3.1-fast-generate-001"

# Known Veo models on Vertex AI — update as Google releases new versions.
SUPPORTED_MODELS: dict[str, dict] = {
    "veo-3.1-generate-001": {
        "display_name": "Veo 3.1",
        "description": "Latest stable Veo 3.1 — highest quality video generation.",
        "supported_locations": ["us-central1"],
        "supports_audio": True,
        "price_per_second_usd": 0.60,
    },
    "veo-3.1-fast-generate-001": {
        "display_name": "Veo 3.1 Fast",
        "description": "Veo 3.1 optimised for speed with reduced latency.",
        "supported_locations": ["us-central1"],
        "supports_audio": True,
        "price_per_second_usd": 0.40,
    },
    "veo-3.1-generate-preview": {
        "display_name": "Veo 3.1 Preview",
        "description": "Preview channel for Veo 3.1.",
        "supported_locations": ["us-central1"],
        "supports_audio": True,
        "price_per_second_usd": 0.60,
    },
    "veo-3.1-fast-generate-preview": {
        "display_name": "Veo 3.1 Fast Preview",
        "description": "Preview channel for Veo 3.1 Fast.",
        "supported_locations": ["us-central1"],
        "supports_audio": True,
        "price_per_second_usd": 0.40,
    },
    "veo-3.0-generate-001": {
        "display_name": "Veo 3",
        "description": "Stable Veo 3.0 — improved quality and motion fidelity over Veo 2.",
        "supported_locations": ["us-central1"],
        "supports_audio": True,
        "price_per_second_usd": 0.50,
    },
    "veo-3.0-generate-preview": {
        "display_name": "Veo 3 Preview",
        "description": "Preview channel for Veo 3.0.",
        "supported_locations": ["us-central1"],
        "supports_audio": True,
        "price_per_second_usd": 0.50,
    },
    "veo-2.0-generate-001": {
        "display_name": "Veo 2",
        "description": "Stable Veo 2.0 — reliable video generation, supports global location.",
        "supported_locations": ["us-central1", "global"],
        "supports_audio": False,
        "price_per_second_usd": 0.35,
    },
}

# Audio surcharge on top of base price (estimate)
_AUDIO_SURCHARGE_PER_SECOND = 0.01


def _load_credentials() -> service_account.Credentials:
    credentials_file = settings.vertex_ai_credentials_file
    if not Path(credentials_file).exists():
        raise FileNotFoundError(
            f"Vertex AI service account key not found: {credentials_file!r}. "
            "Set VERTEX_AI_CREDENTIALS_FILE in .env to a valid path."
        )
    return service_account.Credentials.from_service_account_file(
        credentials_file, scopes=_SCOPES
    )


def init_vertex() -> None:
    """Validate GCP credentials at application startup (fail-fast)."""
    _load_credentials()
    logger.info(
        "GCP credentials OK  project=%s  location=%s",
        settings.gcp_project,
        settings.gcp_location,
    )


def _authed_session() -> google.auth.transport.requests.AuthorizedSession:
    creds = _load_credentials()
    return google.auth.transport.requests.AuthorizedSession(creds)


def _model_endpoint(method: str, model_id: str = DEFAULT_MODEL) -> str:
    base = f"https://{settings.gcp_location}-aiplatform.googleapis.com/v1"
    path = (
        f"/projects/{settings.gcp_project}"
        f"/locations/{settings.gcp_location}"
        f"/publishers/google/models/{model_id}"
    )
    return f"{base}{path}:{method}"


def _check_response(resp: requests.Response) -> None:
    """Raise a domain exception for non-2xx responses."""
    if resp.ok:
        return
    body = resp.text
    if resp.status_code == 400 or "safety" in body.lower() or "blocked" in body.lower():
        raise VertexSafetyError(body)
    raise VertexAPIError(f"HTTP {resp.status_code}: {body}")


def _submit_generation(
    session: google.auth.transport.requests.AuthorizedSession,
    task: "GenerationTask",
    prompt: str,
    duration: int,
    model_id: str = DEFAULT_MODEL,
    config: "VideoGenerationConfig | None" = None,
    image_gcs_uri: str | None = None,
    subject_description: str | None = None,
    video_gcs_uri: str | None = None,
    mask_gcs_uri: str | None = None,
) -> str:
    """POST to predictLongRunning and return the operation name."""
    from app.schemas.video_schema import GenerationTask, VideoGenerationConfig  # avoid circular

    cfg = config or VideoGenerationConfig()

    # Build instance based on task type
    instance: dict[str, Any] = {"prompt": prompt}

    if task == GenerationTask.IMAGE_TO_VIDEO:
        instance["image"] = {"gcsUri": image_gcs_uri}

    elif task == GenerationTask.REFERENCE_SUBJECT:
        instance["referenceImages"] = [
            {
                "referenceType": "REFERENCE_TYPE_SUBJECT",
                "referenceImage": {"gcsUri": image_gcs_uri},
                **({"subjectImageConfig": {"subjectDescription": subject_description}} if subject_description else {}),
            }
        ]

    elif task == GenerationTask.REFERENCE_STYLE:
        instance["referenceImages"] = [
            {
                "referenceType": "REFERENCE_TYPE_STYLE",
                "referenceImage": {"gcsUri": image_gcs_uri},
            }
        ]

    elif task == GenerationTask.VIDEO_EXTENSION:
        instance["video"] = {"gcsUri": video_gcs_uri}

    elif task in (GenerationTask.INPAINT_INSERT, GenerationTask.INPAINT_REMOVE):
        instance["video"] = {"gcsUri": video_gcs_uri}
        instance["mask"] = {"gcsUri": mask_gcs_uri}

    parameters: dict[str, Any] = {
        "durationSeconds": duration,
        "sampleCount": cfg.sample_count,
        "aspectRatio": cfg.aspect_ratio,
    }
    if cfg.resolution:
        parameters["resolution"] = cfg.resolution
    # Always send generateAudio explicitly; omitting it defaults to True on Veo 3.x models
    parameters["generateAudio"] = bool(
        cfg.generate_audio and SUPPORTED_MODELS.get(model_id, {}).get("supports_audio")
    )
    if cfg.seed is not None:
        parameters["seed"] = cfg.seed
    if cfg.storage_uri:
        parameters["storageUri"] = cfg.storage_uri

    body = {
        "instances": [instance],
        "parameters": parameters,
    }
    resp = session.post(_model_endpoint("predictLongRunning", model_id), json=body, timeout=60)
    _check_response(resp)
    return resp.json()["name"]


def _poll_until_done(
    session: google.auth.transport.requests.AuthorizedSession,
    operation_name: str,
    model_id: str = DEFAULT_MODEL,
) -> dict:
    """Poll fetchPredictOperation until done or timeout."""
    elapsed = 0
    while elapsed < _MAX_WAIT_S:
        time.sleep(_POLL_INTERVAL_S)
        elapsed += _POLL_INTERVAL_S

        resp = session.post(
            _model_endpoint("fetchPredictOperation", model_id),
            json={"operationName": operation_name},
            timeout=30,
        )
        _check_response(resp)
        data = resp.json()

        if data.get("error"):
            err = data["error"]
            raise VertexAPIError(f"{err.get('code')}: {err.get('message')}")

        if data.get("done"):
            logger.info("Operation completed. result.keys=%s  response.keys=%s",
                        list(data.keys()), list(data.get("response", {}).keys()))
            return data

        logger.info("Waiting for generation...  %ds elapsed", elapsed)

    raise VertexTimeoutError(f"Generation did not complete within {_MAX_WAIT_S}s.")


def _extract_video_bytes(result: dict) -> bytes:
    """Pull video bytes out of the operation result, downloading from GCS if needed.

    Handles two response shapes returned by different Veo model versions:
    1. generatedSamples[].video  (Veo 3.x GenerateVideoResponse)
    2. predictions[]             (standard PredictResponse / older models)
    """
    response = result.get("response", {})

    # Log top-level keys to help diagnose response shape issues
    logger.debug(
        "Extracting video — result top-level keys: %s  |  response top-level keys: %s",
        list(result.keys()),
        list(response.keys()),
    )

    # Check RAI filtering first — applies to all response shapes
    rai_filtered = response.get("raiMediaFilteredCount", 0)
    if rai_filtered and not response.get("videos") and not response.get("generatedSamples") and not response.get("predictions"):
        raise VertexSafetyError(
            f"All {rai_filtered} generated sample(s) were blocked by the safety filter."
        )

    # ── Shape 0: videos (Veo 3.x fetchPredictOperation actual response) ─────────
    videos = response.get("videos", [])
    if videos:
        video = videos[0]
        logger.debug("videos[0] keys: %s", list(video.keys()))
        encoded = video.get("bytesBase64Encoded") or video.get("encodedContent")
        if encoded:
            logger.info("Found inline base64 video in videos[] (%d chars)", len(encoded))
            return base64.b64decode(encoded)
        gcs_uri = video.get("uri") or video.get("gcsUri")
        if gcs_uri:
            logger.info("Downloading video from GCS (videos[]): %s", gcs_uri)
            return _download_from_gcs(gcs_uri)

    # ── Shape 1: generatedSamples ─────────────────────────────────────────────
    samples = response.get("generatedSamples", [])
    if samples:
        sample = samples[0]
        logger.debug("Sample keys: %s", list(sample.keys()))
        # Use "video" sub-dict if present, otherwise fall back to the sample itself
        # (some API versions put bytesBase64Encoded directly on the sample object)
        video_node = sample.get("video", sample)
        logger.debug("video_node keys: %s", list(video_node.keys()) if isinstance(video_node, dict) else type(video_node))
        encoded = video_node.get("bytesBase64Encoded") or video_node.get("encodedContent")
        if encoded:
            logger.info("Found inline base64 video (%d chars)", len(encoded))
            return base64.b64decode(encoded)
        gcs_uri = video_node.get("uri") or video_node.get("gcsUri")
        if gcs_uri:
            logger.info("Downloading video from GCS: %s", gcs_uri)
            return _download_from_gcs(gcs_uri)

    # Check if RAI filtering removed all samples
    rai_filtered = response.get("raiMediaFilteredCount", 0)
    if rai_filtered:
        raise VertexSafetyError(
            f"All {rai_filtered} generated sample(s) were blocked by the safety filter."
        )

    # ── Shape 2: predictions (standard PredictResponse) ───────────────────────
    predictions = response.get("predictions", [])
    if predictions:
        pred = predictions[0]
        encoded = (
            pred.get("bytesBase64Encoded")
            or pred.get("encodedContent")
            or pred.get("video", {}).get("bytesBase64Encoded")
            or pred.get("video", {}).get("encodedContent")
        )
        if encoded:
            logger.info("Found inline base64 video in predictions (%d chars)", len(encoded))
            return base64.b64decode(encoded)
        gcs_uri = pred.get("gcsUri") or pred.get("uri")
        if gcs_uri:
            logger.info("Downloading video from GCS (predictions): %s", gcs_uri)
            return _download_from_gcs(gcs_uri)

    # Nothing found — log the full structure (keys only to avoid flooding logs)
    logger.error(
        "No video found in Vertex AI response.  result.keys=%s  response.keys=%s  "
        "generatedSamples=%s  predictions=%s",
        list(result.keys()),
        list(response.keys()),
        samples,
        predictions,
    )
    raise NoVideoGeneratedError("No generated samples in Vertex AI response.")


def _download_from_gcs(gcs_uri: str) -> bytes:
    """Download a gs:// object and return its raw bytes."""
    from google.cloud import storage  # transitive dep of google-cloud-aiplatform

    without_scheme = gcs_uri.removeprefix("gs://")
    bucket_name, _, blob_name = without_scheme.partition("/")
    client = storage.Client(project=settings.gcp_project)
    return client.bucket(bucket_name).blob(blob_name).download_as_bytes()


def list_models(check_live: bool = False) -> list[dict]:
    """
    Return the list of supported Veo models.
    If check_live=True, probe each model endpoint to verify availability
    at the currently configured location.
    """
    results = []
    session = _authed_session() if check_live else None

    for model_id, info in SUPPORTED_MODELS.items():
        entry: dict = {
            "model_id": model_id,
            "display_name": info["display_name"],
            "description": info["description"],
            "supported_locations": info["supported_locations"],
            "active_at_current_location": settings.gcp_location in info["supported_locations"],
            "supports_audio": info.get("supports_audio", False),
            "price_per_second_usd": info.get("price_per_second_usd", 0.0),
        }
        if check_live and session is not None:
            if not entry["active_at_current_location"]:
                entry["live_status"] = "not_supported_at_location"
            else:
                try:
                    # Publisher models are global resources — probe via us-central1 endpoint.
                    # For "global" location, veo-2.0 is the only model that works there;
                    # we skip probing for models explicitly not in supported_locations.
                    probe_host = (
                        settings.gcp_location
                        if settings.gcp_location != "global"
                        else "us-central1"
                    )
                    url = (
                        f"https://{probe_host}-aiplatform.googleapis.com/v1"
                        f"/publishers/google/models/{model_id}"
                    )
                    resp = session.get(url, timeout=10)
                    entry["live_status"] = "available" if resp.ok else f"unavailable (HTTP {resp.status_code})"
                except Exception as exc:  # noqa: BLE001
                    entry["live_status"] = f"check_failed: {exc}"
        results.append(entry)

    return results


def generate_video(
    prompt: str,
    duration: int,
    model: str = DEFAULT_MODEL,
    task: "Any | None" = None,
    config: "Any | None" = None,
    image_gcs_uri: str | None = None,
    subject_description: str | None = None,
    video_gcs_uri: str | None = None,
    mask_gcs_uri: str | None = None,
) -> Path:
    """
    Submit a Veo generation job, wait for it to complete, save the video
    locally, and return its Path.

    Raises:
        VertexSafetyError     — prompt rejected by the safety filter.
        VertexTimeoutError    — job did not finish within _MAX_WAIT_S seconds.
        VertexAPIError        — any other API-level failure.
        NoVideoGeneratedError — job succeeded but no usable video was returned.
    """
    if model not in SUPPORTED_MODELS:
        raise VertexAPIError(
            f"Unknown model {model!r}. Supported: {list(SUPPORTED_MODELS)}"
        )

    session = _authed_session()

    logger.info(
        "Submitting Veo generation  task=%s  model=%s  duration=%ds  prompt=%.80s",
        task,
        model,
        duration,
        prompt,
    )

    try:
        operation_name = _submit_generation(
            session, task, prompt, duration, model, config,
            image_gcs_uri, subject_description, video_gcs_uri, mask_gcs_uri,
        )
        logger.info("Operation started: %s", operation_name)
        result = _poll_until_done(session, operation_name, model)
    except (VertexSafetyError, VertexTimeoutError, VertexAPIError, NoVideoGeneratedError):
        raise
    except requests.RequestException as exc:
        raise VertexAPIError(str(exc)) from exc

    video_bytes = _extract_video_bytes(result)
    output_path = build_output_path()
    output_path.write_bytes(video_bytes)
    logger.info("Saved video (%d bytes) to %s", len(video_bytes), output_path)
    return output_path


def estimate_cost(
    model_id: str,
    duration_s: int,
    sample_count: int,
    generate_audio: bool,
) -> dict:
    """Return a rough cost estimate for a generation job."""
    info = SUPPORTED_MODELS.get(model_id, {})
    per_second = info.get("price_per_second_usd", 0.50)
    supports_audio = info.get("supports_audio", False)
    if generate_audio and supports_audio:
        per_second += _AUDIO_SURCHARGE_PER_SECOND
    total = round(per_second * duration_s * sample_count, 4)
    return {
        "model_id": model_id,
        "duration_s": duration_s,
        "sample_count": sample_count,
        "generate_audio": generate_audio and supports_audio,
        "per_second_usd": per_second,
        "estimated_usd": total,
        "note": (
            "Estimates are approximate and may not reflect current pricing. "
            "See https://cloud.google.com/vertex-ai/generative-ai/pricing for details."
        ),
    }


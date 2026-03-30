"""Google Cloud TTS service using the project service account credentials."""
import base64
from pathlib import Path

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account as sa

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


def _voice_name_from_ui_alias(voice: str) -> str:
    if voice.startswith("vi-VN-") or voice.startswith("en-US-"):
        return voice
    # Legacy aliases
    mapping = {
        "alloy": "en-US-Neural2-J",
        "echo": "en-US-Neural2-D",
        "fable": "en-US-Neural2-A",
        "onyx": "en-US-Neural2-J",
        "nova": "en-US-Neural2-A",
        "shimmer": "en-US-Neural2-A",
    }
    return mapping.get(voice, "en-US-Neural2-J")


def _lang_code_from_voice(voice_name: str) -> str:
    if voice_name.startswith("vi-VN-"):
        return "vi-VN"
    return "en-US"


def _get_access_token() -> str:
    creds = sa.Credentials.from_service_account_file(
        settings.vertex_ai_credentials_file,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(GoogleAuthRequest())
    return creds.token


async def synthesize_speech(
    script: str,
    output_path: str,
    voice: str = "onyx",
    model: str = "google-cloud-tts",
) -> dict:
    """
    Generate a voiceover MP3 from a script.

    Returns:
        {"audio_path": str, "timestamps": list[{"word": str, "start": float, "end": float}]}
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    resolved_voice = _voice_name_from_ui_alias(voice)
    lang_code = _lang_code_from_voice(resolved_voice)

    token = _get_access_token()
    url = "https://texttospeech.googleapis.com/v1/text:synthesize"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "input": {"text": script},
        "voice": {
            "languageCode": lang_code,
            "name": resolved_voice,
        },
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.1, "pitch": 0.0},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    audio_b64 = data.get("audioContent")
    if not audio_b64:
        raise ValueError("Google TTS response missing audioContent")

    out.write_bytes(base64.b64decode(audio_b64))
    logger.info("Google TTS saved -> %s (voice=%s lang=%s)", out, resolved_voice, lang_code)

    timestamps = _estimate_word_timestamps(script)
    return {"audio_path": str(out), "timestamps": timestamps}


def _estimate_word_timestamps(script: str, wpm: int = 145) -> list[dict]:
    # Lightweight fallback for subtitle timing when no ASR pass is used.
    words = [w for w in script.split() if w.strip()]
    if not words:
        return []
    sec_per_word = 60.0 / max(1, wpm)
    result: list[dict] = []
    t = 0.0
    for w in words:
        start = t
        end = t + sec_per_word
        result.append({"word": w, "start": round(start, 3), "end": round(end, 3)})
        t = end
    return result

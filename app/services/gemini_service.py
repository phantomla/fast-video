import json
import re
from json import JSONDecodeError

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_VERTEX_URL_TPL = (
    "https://{host}/v1/projects/{project}"
    "/locations/{location}/publishers/google/models/{model}:generateContent"
)

_SUPPORTED_DURATIONS = (4, 6, 8)

_BRAIN_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "required": ["intro_phrase", "visuals", "vibe", "bg_music_suggestion"],
    "properties": {
        "intro_phrase": {"type": "STRING"},
        "visuals": {
            "type": "ARRAY",
            "minItems": 4,
            "maxItems": 5,
            "items": {
                "type": "OBJECT",
                "required": ["prompt", "duration", "landmark_name"],
                "properties": {
                    "prompt": {"type": "STRING"},
                    "duration": {"type": "INTEGER", "enum": [4, 6, 8]},
                    "landmark_name": {"type": "STRING"},
                },
            },
        },
        "vibe": {"type": "STRING"},
        "bg_music_suggestion": {"type": "STRING"},
    },
}


def _vertex_host(location: str) -> str:
    # Global uses the shared endpoint host, regional locations use {location}-aiplatform.
    if location == "global":
        return "aiplatform.googleapis.com"
    return f"{location}-aiplatform.googleapis.com"

_VEO_PROMPT_FORMULA = """\
Every Veo prompt MUST follow this formula:
  [UNIQUE CAMERA MOVE] + [CITY-SPECIFIC FUTURISTIC SUBJECT] + [ATMOSPHERE] + [QUALITY TAGS]

Camera moves (each shot must use a DIFFERENT one):
  sweeping aerial drone shot | slow cinematic dolly forward | bird's-eye view slow pan |
  low-altitude flyover | wide establishing shot | slow crane up reveal | tracking shot along skyline

Atmosphere (each shot must use a DIFFERENT one):
  blue-hour ambient glow | golden-hour cinematic lighting | dramatic overcast storm light |
  night city neon bloom | sunrise warm diffused haze | twilight purple sky

Quality tags (always append to every prompt):
  cinematic, photorealistic, ultra-detailed, 8K, no people, no text, no watermark
"""

_BRAIN_PROMPT = (
    'You are a Veo video director creating a futuristic "What If" YouTube Shorts video.\n\n'
    "Topic: __TOPIC__\n\n"
    "Task: Generate 4-5 cinematic shots for a 16-20 second vertical Shorts video imagining __TOPIC__ transformed far into the future.\n\n"
    "__VEO_GUIDE__\n"
    "Shot structure:\n"
    "- Shot 1: Wide aerial overview of the entire city skyline — establish the futuristic scale. landmark_name = \"\"\n"
    "- Shots 2-5: Pick 3-4 of the most ICONIC and RECOGNIZABLE areas/landmarks of __TOPIC__ and reimagine each one as a futuristic megacity location. Choose areas specific to THIS city — not generic subjects. Each shot reveals a different part of the city.\n\n"
    "Return ONLY a valid JSON object (no markdown, no explanation):\n"
    '{\n'
    '  "intro_phrase": "<punchy 6-8 word question in __LANG__, e.g. What would Tokyo look like in 3000?>",\n'
    '  "visuals": [\n'
    '    {"prompt": "<shot prompt following the formula>", "duration": 4, "landmark_name": ""},\n'
    '    {"prompt": "<shot prompt following the formula>", "duration": 4, "landmark_name": "<iconic area name, 2-4 words>"},\n'
    '    {"prompt": "<shot prompt following the formula>", "duration": 4, "landmark_name": "<iconic area name, 2-4 words>"},\n'
    '    {"prompt": "<shot prompt following the formula>", "duration": 4, "landmark_name": "<iconic area name, 2-4 words>"},\n'
    '    {"prompt": "<shot prompt following the formula — optional 5th shot>", "duration": 4, "landmark_name": "<iconic area name, 2-4 words>"}\n'
    '  ],\n'
    '  "vibe": "<music genre that fits this city\'s futuristic vibe>",\n'
    '  "bg_music_suggestion": "<specific style description>"\n'
    '}\n\n'
    "Hard rules:\n"
    "- Each shot MUST use a DIFFERENT camera move AND a DIFFERENT atmosphere — no repeats\n"
    "- Shots 2-5: subjects must be SPECIFIC to __TOPIC__ (real iconic areas reimagined), not generic city elements\n"
    "- NO historical monuments, temples, ruins, war memorials — futuristic only\n"
    "- NO faces, no text in scene, no watermarks\n"
    "- All durations = 4\n"
    "- intro_phrase in __LANG__; landmark_name values in __LANG__"
)


def _build_payload(prompt_text: str, use_schema: bool = True) -> dict:
    generation_config = {
        "temperature": 0.5,
        "maxOutputTokens": 1536,
        "responseMimeType": "application/json",
    }
    if use_schema:
        generation_config["responseSchema"] = _BRAIN_RESPONSE_SCHEMA

    return {
        "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
        "generationConfig": generation_config,
    }


def _normalize_duration(value: int | str | None) -> int:
    try:
        d = int(value) if value is not None else 6
    except (TypeError, ValueError):
        d = 6
    return min(_SUPPORTED_DURATIONS, key=lambda s: abs(s - d))


def _clean_raw_text(raw_text: str) -> str:
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
    raw_text = re.sub(r"\s*```$", "", raw_text.strip())
    return raw_text.strip()


def _extract_json_object(raw_text: str) -> str:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return raw_text
    return raw_text[start : end + 1]


def _extract_raw_text(data: dict) -> str:
    try:
        return data["candidates"][0]["content"]["parts"][0].get("text", "")
    except Exception:  # noqa: BLE001
        return ""


def _cleanup_json_string(value: str) -> str:
    v = value.strip()
    v = v.replace('\\"', '"').replace("\\n", " ")
    return re.sub(r"\s+", " ", v).strip()


def _fallback_brain(topic: str, language: str) -> dict:
    intro = f"What would {topic} look like in the future?"
    areas = ["Old Quarter", "Central Lake", "City Center"]
    return {
        "intro_phrase": intro,
        "visuals": [
            {
                "prompt": (
                    f"Futuristic {topic} megacity aerial drone overview, glass towers, flying vehicles, "
                    "hyper-realistic, 8k, atmospheric neon lighting, slow pan, no text"
                ),
                "duration": 4,
                "landmark_name": "",
            },
            {
                "prompt": (
                    f"Futuristic urban district of {topic}, holographic billboards, elevated sky-parks, "
                    "cinematic wide, hyper-realistic, 8k, dramatic sky, no text"
                ),
                "duration": 4,
                "landmark_name": areas[0],
            },
            {
                "prompt": (
                    f"Iconic lake or river of {topic} with futuristic city skyline backdrop, "
                    "glowing reflections, flying taxis, cinematic wide, 8k, no text"
                ),
                "duration": 4,
                "landmark_name": areas[1],
            },
            {
                "prompt": (
                    f"Futuristic central plaza and commercial district of {topic}, "
                    "crowds, neon lights, autonomous pods, vertical gardens, cinematic, 8k, no text"
                ),
                "duration": 4,
                "landmark_name": areas[2],
            },
        ],
        "vibe": "Cyberpunk Phonk",
        "bg_music_suggestion": "Phonk-Phonk-pr.mp3",
    }


def _salvage_brain_from_text(raw_text: str, topic: str, language: str) -> dict:
    text = _clean_raw_text(raw_text)
    if not text:
        return _fallback_brain(topic, language)

    intro_match = re.search(r'"intro_phrase"\s*:\s*"([\s\S]*?)"\s*(?:,|})', text)
    prompts = re.findall(r'"prompt"\s*:\s*"([\s\S]*?)"\s*(?:,|})', text)
    durations = re.findall(r'"duration"\s*:\s*(\d+)', text)
    landmarks = re.findall(r'"landmark_name"\s*:\s*"([\s\S]*?)"\s*(?:,|})', text)
    vibe_match = re.search(r'"vibe"\s*:\s*"([\s\S]*?)"\s*(?:,|})', text)
    music_match = re.search(r'"bg_music_suggestion"\s*:\s*"([\s\S]*?)"\s*(?:,|})', text)

    result = _fallback_brain(topic, language)

    if intro_match:
        result["intro_phrase"] = _cleanup_json_string(intro_match.group(1))
    if vibe_match:
        result["vibe"] = _cleanup_json_string(vibe_match.group(1))
    if music_match:
        result["bg_music_suggestion"] = _cleanup_json_string(music_match.group(1))

    if prompts:
        visuals = []
        for i in range(min(5, len(prompts))):
            visuals.append(
                {
                    "prompt": _cleanup_json_string(prompts[i]),
                    "duration": _normalize_duration(durations[i] if i < len(durations) else 4),
                    "landmark_name": _cleanup_json_string(landmarks[i]) if i < len(landmarks) else "",
                }
            )
        while len(visuals) < 4:
            visuals.append(result["visuals"][len(visuals)])
        result["visuals"] = visuals

    return result


def _parse_response(data: dict) -> dict:
    raw_text = _extract_raw_text(data)
    raw_text = _clean_raw_text(raw_text)

    parse_errors: list[Exception] = []
    for candidate in (raw_text, _extract_json_object(raw_text)):
        if not candidate:
            continue
        try:
            result = json.loads(candidate)
            break
        except JSONDecodeError as exc:
            parse_errors.append(exc)
    else:
        preview = raw_text[:240].replace("\n", " ")
        logger.warning("Gemini returned invalid JSON: %s", preview)
        raise parse_errors[-1] if parse_errors else ValueError("Gemini response had no parseable JSON")

    if "intro_phrase" not in result or "visuals" not in result:
        raise ValueError("Gemini response missing required keys: intro_phrase/visuals")

    if not isinstance(result["visuals"], list) or not result["visuals"]:
        raise ValueError("Gemini visuals must be a non-empty list")

    for visual in result["visuals"]:
        visual["duration"] = _normalize_duration(visual.get("duration"))

    logger.info("Gemini response: vibe=%s, intro_phrase=%r", result.get("vibe"), result.get("intro_phrase", ""))
    return result


async def generate_brain(topic: str, language: str = "en") -> dict:
    prompt_text = (
        _BRAIN_PROMPT
        .replace("__TOPIC__", topic)
        .replace("__LANG__", language)
        .replace("__VEO_GUIDE__", _VEO_PROMPT_FORMULA)
    )
    logger.info(
        "Gemini: using Vertex AI, model=%s, location=%s",
        settings.gemini_model,
        settings.gemini_location,
    )

    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2 import service_account as sa

    creds = sa.Credentials.from_service_account_file(
        settings.vertex_ai_credentials_file,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(GoogleAuthRequest())
    url = _VERTEX_URL_TPL.format(
        host=_vertex_host(settings.gemini_location),
        location=settings.gemini_location,
        project=settings.gcp_project,
        model=settings.gemini_model,
    )
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        last_error: Exception | None = None
        last_raw_text = ""
        use_schema = True
        for attempt in range(1, 4):
            attempt_prompt = prompt_text
            if attempt > 1:
                attempt_prompt += (
                    "\n\nIMPORTANT: Return strict minified JSON only. "
                    "Do not include markdown, comments, or trailing text."
                )

            try:
                resp = await client.post(
                    url,
                    json=_build_payload(attempt_prompt, use_schema=use_schema),
                    headers=headers,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 400 and use_schema:
                    logger.warning("Gemini rejected responseSchema; retrying without schema")
                    use_schema = False
                    last_error = exc
                    continue
                raise

            body = resp.json()
            last_raw_text = _extract_raw_text(body)

            try:
                return _parse_response(body)
            except (JSONDecodeError, ValueError, KeyError, IndexError) as exc:
                last_error = exc
                logger.warning("Gemini JSON parse failed (attempt %d/3): %s", attempt, exc)

        if last_error is not None:
            logger.error("Gemini parse failed after retries, salvaging response: %s", last_error)
            return _salvage_brain_from_text(last_raw_text, topic, language)

    raise RuntimeError("Gemini request loop exited unexpectedly")


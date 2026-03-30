"""Stage 0: Call Gemini to generate voiceover script + Veo visual prompts."""
from app.schemas.whatif_schema import BrainOutput, VisualConfig
from app.services.gemini_service import generate_brain


async def run(topic: str, voice_model: str = "onyx", language: str = "en") -> BrainOutput:
    raw = await generate_brain(topic, language)
    return BrainOutput(
        intro_phrase=raw["intro_phrase"],
        voice_model=voice_model,
        visuals=[VisualConfig(**v) for v in raw["visuals"]],
        vibe=raw.get("vibe", "Cinematic"),
    )

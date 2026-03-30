# WhatIf Factory — Implementation Reference

> **Status:** ✅ Implemented and working.
> Input: 1 topic string → Output: ~20s YouTube Shorts video (9:16) with AI-generated clips and voiceover.

---

## Architecture

```
POST /whatif/start {"topic": "Hà Nội năm 3000"}
          │
          ▼
  create_whatif_job()          ← generates unique job_id, creates work dir
          │
          ▼ (asyncio background task)
  ┌────────────────────────────────────────────┐
  │ stage0_brain.py — Gemini 2.5 Flash          │
  │ topic → intro_phrase + 6 Veo prompts        │
  │         + landmark names + vibe             │
  └─────────────────┬──────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  stage1_veo_gen.py       stage2_tts.py
  asyncio.gather()        asyncio.gather()
  6 clips (4–6s each)     per-clip voiceover MP3s
  clip_00..05.mp4         clip_audio_00..05.mp3
        │                       │
        └───────────┬───────────┘
                    ▼
          stage3_stitch.py
          ffmpeg concat → stitched.mp4
                    │
                    ▼
          stage4_audio_mix.py
          pydub position + ffmpeg mux
          → with_audio.mp4
                    │
                    ▼
          exports/whatif_{job_id}.mp4
```

Stages 1 and 2 run concurrently via `asyncio.gather()`.

---

## Stages

### Stage 0 — Brain (`stage0_brain.py`)

Calls Gemini to produce structured content for exactly 6 shots:

| Shot | Duration | Content |
|---|---|---|
| 0 | 6s | Wide aerial hero shot of entire futuristic city |
| 1–5 | 4s each | Specific real-world landmark, reimagined in the future |

**Gemini prompt rules enforced:**
- Each Veo prompt must describe the real landmark's signature first, then transform it ("visual anchor rule")
- Different camera move for each shot (sweeping aerial, slow dolly, bird's-eye pan, etc.)
- Different atmospheric lighting per shot
- Quality tags always appended: `cinematic, photorealistic, ultra-detailed, 8K, no people, no text, no watermark`
- Landmark names must be ≤ 4 words and refer to real, recognizable places (no generic names)

**Fallback / retry logic:**
1. First attempt: Gemini with full JSON schema constraint
2. On 400: retry without schema
3. On parse failure: retry with stricter JSON instructions
4. If all fail: generate default fallback brain output

**Output schema:**
```python
BrainOutput(
    intro_phrase="punchy 6-8 word hook",
    voice_model="en-US-Neural2-J",
    visuals=[VisualConfig(prompt=..., duration=4|6, landmark_name=...), ...],  # 6 items
    vibe="Cyberpunk Phonk",
    bg_music_suggestion="dark synthwave with bass drops"
)
```

---

### Stage 1 — Veo Generation (`stage1_veo_gen.py`)

Generates all 6 clips in parallel via `asyncio.gather()`.

- Model: configurable (default `veo-3.1-fast-generate-preview`)
- Aspect ratio: 9:16 (vertical)
- Task: TEXT_TO_VIDEO
- Audio: disabled (handled in stage 4)
- Duration: normalized to 4, 6, or 8 seconds

**Negative prompt applied to all clips:**
```
blurry, low quality, camera shake, fast zoom, deformed, cartoon,
text overlays, watermark, distorted faces, nsfw
```

**Output:** `work_dir/clip_00.mp4` … `clip_05.mp4`

---

### Stage 2 — TTS (`stage2_tts.py`)

Generates per-clip voiceover audio, parallel with stage 1.

**Text per clip:**
- Clip 0 → `intro_phrase` (opening hook)
- Clips 1–5 → `landmark_name` from brain output (truncated to 5 words)
- Empty landmark names → no audio for that clip

**Service:** Google Cloud TTS (via Vertex AI credentials)
**Settings:** speaking rate 1.1×, pitch 0.0, MP3 output

**Output:** `work_dir/clip_audio_00.mp3` … `clip_audio_05.mp3`

---

### Stage 3 — Stitch (`stage3_stitch.py`)

Concatenates the 6 clips into a single video using ffmpeg.

```
ffmpeg -i clip_00.mp4 ... -i clip_05.mp4
  -filter_complex "concat=n=6:v=1:a=0[outv]"
  -map [outv] -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p
  stitched.mp4
```

- Video-only (no audio at this stage)
- CRF 16 = very high quality
- **Output:** `work_dir/stitched.mp4`

---

### Stage 4 — Audio Mix (`stage4_audio_mix.py`)

Composites per-clip voiceover onto the stitched video.

1. Get actual clip durations via `ffprobe`
2. Build silent base audio track (pydub) matching video duration
3. Overlay each clip's audio at the correct time offset
4. Export composite as `voiceover.mp3`
5. Mux into video via ffmpeg (audio codec: AAC 320k, video: copy)

**Output:** `work_dir/with_audio.mp4`

---

## Progress mapping

| Stage | Percent range |
|---|---|
| Stage 0 (Gemini) | 5 → 15% |
| Stage 1+2 (Veo + TTS) | 20 → 60% |
| Stage 3 (stitch) | 62 → 72% |
| Stage 4 (audio mix) | 74 → 90% |
| Export + finalize | 90 → 100% |

---

## Job lifecycle

```
queued → running → completed
                 ↘ failed
```

Jobs are stored in-memory (`dict` in `orchestrator.py`). Lost on server restart.

Work directories: `temp/whatif_jobs/wi_YYYYMMDD_{job_id}/`
Final output: `exports/whatif_{job_id}.mp4`

---

## Key files

| File | Role |
|---|---|
| `app/pipeline_whatif/orchestrator.py` | Job store, `run_pipeline()`, SSE event pushing |
| `app/pipeline_whatif/stage0_brain.py` | Gemini script/prompt generation |
| `app/pipeline_whatif/stage1_veo_gen.py` | Veo clip generation |
| `app/pipeline_whatif/stage2_tts.py` | Google Cloud TTS voiceover |
| `app/pipeline_whatif/stage3_stitch.py` | ffmpeg concat |
| `app/pipeline_whatif/stage4_audio_mix.py` | Audio mux |
| `app/api/whatif_routes.py` | `/whatif/*` API endpoints |
| `app/schemas/whatif_schema.py` | Pydantic models |
| `app/services/gemini_service.py` | Vertex AI Gemini HTTP client |
| `app/services/tts_service.py` | Google Cloud TTS client |

---

## Known limitations / future improvements

See README.md for the full improvements list.

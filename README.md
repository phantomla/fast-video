# fast-video

AI video generation service powered by **Google Vertex AI (Veo)**.

Two modes:
- **Single clip** — generate one Veo clip from a prompt (`/generate-one`)
- **WhatIf Factory** — full YouTube Shorts pipeline: topic → AI-scripted + AI-generated video with voiceover (`/whatif/*`)

## Project structure

```
fast-video/
  app/
    main.py                      ← FastAPI app init + router registration
    api/
      routes.py                  ← POST /generate-one
      whatif_routes.py           ← POST /whatif/start, GET /whatif/{id}/events, GET /whatif/{id}/result
    core/
      config.py                  ← Env var validation (pydantic-settings)
      logger.py                  ← Logging setup
    pipeline_whatif/
      orchestrator.py            ← Job management & pipeline coordination
      stage0_brain.py            ← Gemini: topic → script + 6 Veo prompts
      stage1_veo_gen.py          ← Vertex AI Veo: generate 6 video clips (parallel)
      stage2_tts.py              ← Google Cloud TTS: per-clip voiceover (parallel with stage1)
      stage3_stitch.py           ← ffmpeg: concatenate clips into single timeline
      stage4_audio_mix.py        ← ffmpeg + pydub: mux voiceover into video
    services/
      vertex_service.py          ← Vertex AI Veo integration
      gemini_service.py          ← Vertex AI Gemini integration
      tts_service.py             ← Google Cloud TTS integration
      history_service.py         ← SQLite generation history
    schemas/
      video_schema.py            ← Single-clip request/response models
      whatif_schema.py           ← WhatIf job models
    utils/
      file_utils.py              ← UUID filename + exports directory management
  exports/                       ← Final videos saved here
  temp/whatif_jobs/              ← Per-job working directories (auto-created)
  requirements.txt
  Makefile
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `VERTEX_AI_CREDENTIALS_FILE` | **Yes** | Path to GCP service account JSON key |
| `GCP_PROJECT` | **Yes** | Your GCP project ID |
| `GCP_LOCATION` | No | Vertex AI region for Veo (default: `us-central1`) |
| `GEMINI_LOCATION` | No | Gemini endpoint location (default: `global`) |
| `GEMINI_MODEL` | No | Gemini model ID (default: `gemini-2.5-flash-preview-04-17`) |

```bash
export VERTEX_AI_CREDENTIALS_FILE="/path/to/service-account.json"
export GCP_PROJECT="your-project-id"
export GCP_LOCATION="us-central1"   # optional
```

> All three services (Veo, Gemini, Google Cloud TTS) reuse the same service account credentials — no extra keys needed.

## Quick start

### macOS / Linux

```bash
make install   # create venv + install dependencies
make run       # start server on port 8000
make debug     # start server with --reload (hot-reload)
```

### Windows

Two batch files are provided — no manual setup needed.

**Step 1 — Install (run once):**
```
install_windows.bat
```
This will:
- Check for Python 3.11+ and install it via `winget` if missing
- Check for `ffmpeg` and install it via `winget` if missing
- Create a `.venv` virtual environment
- Install all Python dependencies from `requirements.txt`
- Create `exports/` and `temp/whatif_jobs/` directories

**Step 2 — Set environment variables** (required before running):
```bat
set VERTEX_AI_CREDENTIALS_FILE=C:\path\to\service-account.json
set GCP_PROJECT=your-gcp-project-id
```
Or set them permanently via **System Properties → Advanced → Environment Variables**.

**Step 3 — Run:**
```
run_windows.bat
```

The server starts on `http://localhost:8000`.

---

## API — Single Clip

### `POST /generate-one`

Generate a single Veo video clip from a text prompt.

```bash
curl -X POST http://localhost:8000/generate-one \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A lone surfer riding a massive wave at sunset",
    "duration": 5
  }'
```

With optional image reference:

```bash
curl -X POST http://localhost:8000/generate-one \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Slow dramatic lighting over the scene",
    "image_reference_uri": "gs://your-bucket/reference.jpg",
    "duration": 8
  }'
```

**Response:**
```json
{
  "status": "success",
  "file_path": "/abs/path/to/exports/<uuid>.mp4",
  "message": "Video generated successfully"
}
```

**Error codes:**

| HTTP | Cause |
|---|---|
| `400` | Invalid input or safety filter rejection |
| `500` | Missing env var or internal error |
| `502` | Unexpected Vertex AI API error |
| `504` | Request timed out |

---

## API — WhatIf Factory

Full end-to-end pipeline: one topic string → complete YouTube Shorts video (~20s, 9:16, with voiceover).

### Pipeline overview

```
POST /whatif/start {"topic": "Hà Nội năm 3000"}
          ↓
    create job (returns job_id immediately)
          ↓ (background)
  [Stage 0]  Gemini generates: intro phrase + 6 Veo prompts + landmark names
          ↓
  [Stage 1] ──parallel── [Stage 2]
  Veo generates           Google TTS generates
  6 video clips           per-clip voiceover audio
          ↓
  [Stage 3]  ffmpeg concatenates 6 clips → stitched.mp4
          ↓
  [Stage 4]  pydub + ffmpeg mux voiceover → with_audio.mp4
          ↓
    exports/whatif_{job_id}.mp4
```

**Stages 1 and 2 run in parallel** — Veo clip generation and TTS voiceover synthesis happen simultaneously, reducing total pipeline time.

---

### `POST /whatif/start`

Start a new WhatIf job. Returns immediately with a `job_id`.

**Request:**
```json
{
  "topic": "Hà Nội năm 3000",
  "model": "veo-3.1-fast-generate-preview",
  "voice_model": "en-US-Neural2-J",
  "language": "en"
}
```

| Field | Default | Description |
|---|---|---|
| `topic` | required | Topic or question for the video |
| `model` | `veo-3.1-fast-generate-preview` | Veo model variant |
| `voice_model` | `en-US-Neural2-J` | Google Cloud TTS voice |
| `language` | `en` | Language for Gemini script generation (`en` or `vi`) |

**Response `202`:**
```json
{
  "job_id": "a3f9bc12e4d0",
  "status": "queued"
}
```

---

### `GET /whatif/{job_id}/events`

Stream real-time pipeline progress as Server-Sent Events.

```bash
curl -N http://localhost:8000/whatif/a3f9bc12e4d0/events
```

**Event format:**
```
data: {"message": "Generating video clips...", "stage": "veo_gen", "percent": 30}
data: {"message": "TTS complete", "stage": "tts", "percent": 55}
...
data: {"done": true}
```

| Field | Description |
|---|---|
| `message` | Human-readable status |
| `stage` | Internal stage name |
| `percent` | Overall progress 0–100 |
| `done: true` | Pipeline completed successfully |
| `failed: true` | Pipeline failed; includes `error` field |

Keepalive pings are sent every 25 seconds if there is no activity.

---

### `GET /whatif/{job_id}/result`

Get the current state of a job. Can be polled at any time; non-blocking.

**Response:**
```json
{
  "job_id": "a3f9bc12e4d0",
  "status": "completed",
  "output_video": "/exports/whatif_a3f9bc12e4d0.mp4",
  "duration_sec": 22.4,
  "brain_output": {
    "intro_phrase": "What if Hanoi became a megacity?",
    "voice_model": "en-US-Neural2-J",
    "visuals": [...],
    "vibe": "Cyberpunk Phonk"
  },
  "error": null
}
```

| Status | Meaning |
|---|---|
| `queued` | Job created, not yet started |
| `running` | Pipeline in progress |
| `completed` | Video ready at `output_video` |
| `failed` | Error in `error` field |

---

### Supported voices

| Voice name | Language | Style |
|---|---|---|
| `en-US-Neural2-J` | English (US) | Male, deep |
| `en-US-Neural2-D` | English (US) | Male, neutral |
| `en-US-Neural2-A` | English (US) | Female |
| `vi-VN-Neural2-A` | Vietnamese | Female |
| `vi-VN-Neural2-D` | Vietnamese | Male |

Legacy aliases (`onyx`, `alloy`, `echo`, `fable`, `nova`, `shimmer`) are also accepted and map to English Neural2 voices.

---

### Example: full flow

```bash
# 1. Start job
JOB=$(curl -s -X POST http://localhost:8000/whatif/start \
  -H "Content-Type: application/json" \
  -d '{"topic": "Tokyo in the year 3000", "language": "en"}' \
  | jq -r .job_id)

# 2. Stream progress
curl -N http://localhost:8000/whatif/$JOB/events

# 3. Get result
curl http://localhost:8000/whatif/$JOB/result | jq .output_video
```

---

## Output

| Type | Location |
|---|---|
| Single clip | `./exports/<uuid>.mp4` |
| WhatIf video | `./exports/whatif_<job_id>.mp4` |
| Temp work files | `./temp/whatif_jobs/wi_YYYYMMDD_<job_id>/` |

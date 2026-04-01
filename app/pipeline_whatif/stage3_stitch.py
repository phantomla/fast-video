"""Stage 3: ffmpeg stitch — concatenate clips at original speed (no slow-mo)."""
import subprocess
from pathlib import Path

from app.schemas.whatif_schema import WhatIfJob
from app.core.logger import get_logger

logger = get_logger(__name__)


def run(job: WhatIfJob, work_dir: Path) -> str:
    clips = job.clip_paths
    if not clips:
        raise RuntimeError(f"[{job.job_id}] No clips to stitch")

    # ── Timeline hook: prepend last 1.5 s of the last clip as a teaser ──────
    all_clips: list[str] = list(clips)
    if job.topic_type == "timeline" and len(clips) > 1:
        last_clip = clips[-1]
        snippet_path = str(work_dir / "hook_snippet.mp4")
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", last_clip],
            capture_output=True, text=True, check=True,
        )
        last_dur = float(probe.stdout.strip())
        ss = max(0.0, last_dur - 1.5)
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{ss:.3f}", "-i", last_clip,
             "-t", "1.5", "-c:v", "libx264", "-crf", "16", "-preset", "fast",
             "-pix_fmt", "yuv420p", snippet_path],
            check=True, capture_output=True,
        )
        probe2 = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", snippet_path],
            capture_output=True, text=True, check=True,
        )
        snippet_ms = int(float(probe2.stdout.strip()) * 1000)
        job.audio_offset_ms = snippet_ms
        all_clips = [snippet_path] + list(clips)
        logger.info(
            "[%s] Timeline hook snippet: %dms prepended from end of last clip",
            job.job_id, snippet_ms,
        )
    # ────────────────────────────────────────────────────────────────────────

    inputs = []
    for clip in all_clips:
        inputs += ["-i", clip]

    concat_refs = "".join(f"[{i}:v]" for i in range(len(all_clips)))
    concat_filter = f"{concat_refs}concat=n={len(all_clips)}:v=1:a=0[outv]"

    out_path = str(work_dir / "stitched.mp4")
    cmd = (
        ["ffmpeg", "-y"]
        + inputs
        + ["-filter_complex", concat_filter,
           "-map", "[outv]",
           "-c:v", "libx264",
           "-crf", "16",
           "-preset", "slow",
           "-pix_fmt", "yuv420p",
           "-movflags", "+faststart",
           out_path]
    )
    logger.info("[%s] ffmpeg stitch %d clips: %s", job.job_id, len(all_clips), " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info("[%s] Stitched → %s", job.job_id, out_path)
    return out_path

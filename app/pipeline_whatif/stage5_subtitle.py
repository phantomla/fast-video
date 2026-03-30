"""
Stage 5: Burn subtitles using Pillow-rendered PNG overlays + ffmpeg overlay filter.

This approach bypasses ffmpeg's drawtext/subtitles filters entirely (which require
libfreetype/libass that are not compiled into the Homebrew ffmpeg build).
Instead:
  1. Pillow renders each subtitle line as a full-frame transparent RGBA PNG.
  2. ffmpeg's `overlay` filter chains those PNGs onto the video with per-subtitle timing.
Pillow handles Unicode/Vietnamese natively via Arial Unicode.ttf.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.schemas.whatif_schema import WhatIfJob
from app.core.logger import get_logger

logger = get_logger(__name__)

_FONT_SIZE = 52
_BORDER = 3           # outline thickness in pixels
_MAX_CHARS = 28       # max chars per subtitle line
_WORDS_PER_MIN = 130  # fallback estimate
_Y_RATIO = 0.72       # 72% down — safe for Shorts

_FONT_SEARCH = [
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_SEARCH:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    logger.warning("No TrueType font found; falling back to PIL default (no Unicode support)")
    return ImageFont.load_default()


def _render_png(text: str, out_path: Path, vid_w: int, vid_h: int) -> None:
    """Render *text* centered at _Y_RATIO height as a full-frame transparent RGBA PNG."""
    img = Image.new("RGBA", (vid_w, vid_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(_FONT_SIZE)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (vid_w - text_w) // 2
    y = int(vid_h * _Y_RATIO) - text_h // 2

    # Draw black outline by offsetting in all 8 directions
    for dx in range(-_BORDER, _BORDER + 1):
        for dy in range(-_BORDER, _BORDER + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    img.save(str(out_path), "PNG")


def _video_dimensions(video_path: str) -> tuple[int, int]:
    probe = subprocess.run(
        ["ffprobe", "-v", "error",
         "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0",
         video_path],
        capture_output=True, text=True,
    )
    parts = probe.stdout.strip().split(",")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return 1080, 1920


def _estimate_timestamps(script: str) -> list[dict]:
    words = script.split()
    sec_per_word = 60.0 / _WORDS_PER_MIN
    timestamps, t = [], 0.5
    for word in words:
        dur = sec_per_word * (1 + len(word) / 12)
        timestamps.append({"word": word, "start": t, "end": t + dur})
        t += dur + 0.04
    return timestamps


def _group_lines(timestamps: list[dict]) -> list[dict]:
    lines, current, start = [], [], None
    char_count = 0
    for t in timestamps:
        word = t["word"]
        if start is None:
            start = t["start"]
        if char_count + len(word) + 1 > _MAX_CHARS and current:
            lines.append({"text": " ".join(current), "start": start, "end": t["start"]})
            current, char_count, start = [word], len(word), t["start"]
        else:
            current.append(word)
            char_count += len(word) + 1
    if current:
        end = timestamps[-1]["end"] if timestamps else (start or 0) + 3.0
        lines.append({"text": " ".join(current), "start": start, "end": end})
    return lines


def run(job: WhatIfJob, video_path: str, work_dir: Path) -> str:
    timestamps = job.voiceover_timestamps or []
    if not timestamps:
        logger.info("[%s] No Whisper timestamps — estimating", job.job_id)
        timestamps = _estimate_timestamps(job.brain_output.script)

    subtitles = _group_lines(timestamps)
    if not subtitles:
        logger.warning("[%s] No subtitle lines, skipping stage 5", job.job_id)
        return video_path

    vid_w, vid_h = _video_dimensions(video_path)

    # Render one PNG per subtitle line
    png_dir = work_dir / "sub_pngs"
    png_dir.mkdir(exist_ok=True)
    png_paths: list[Path] = []
    for i, sub in enumerate(subtitles):
        p = png_dir / f"sub_{i:03d}.png"
        _render_png(sub["text"], p, vid_w, vid_h)
        png_paths.append(p)

    # Build ffmpeg command:
    # Inputs: [0]=video, [1..N]=subtitle PNGs (looped stills)
    # filter_complex: chain overlay filters, each enabled only during its time window
    cmd = ["ffmpeg", "-y", "-i", video_path]
    for p in png_paths:
        cmd += ["-loop", "1", "-i", str(p)]

    n = len(subtitles)
    filter_parts = []
    for i, sub in enumerate(subtitles):
        in_tag  = "[0:v]" if i == 0 else f"[ov{i}]"
        out_tag = f"[ov{i+1}]" if i < n - 1 else "[outv]"
        s, e = sub["start"], sub["end"]
        filter_parts.append(
            f"{in_tag}[{i + 1}:v]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'{out_tag}"
        )

    out_path = str(work_dir / "final.mp4")
    cmd += [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[outv]",
        "-map", "0:a?",      # copy audio if present (? = optional)
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        out_path,
    ]

    logger.info("[%s] Burning %d subtitle(s) via overlay filter", job.job_id, n)
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info("[%s] Subtitles burned → %s", job.job_id, out_path)
    return out_path

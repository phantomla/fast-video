"""
history_service.py — SQLite-backed history for video generations.

Uses Python's built-in sqlite3 module; no extra dependencies required.
DB file lives at <project_root>/data/history.db.
"""
import sqlite3
import time
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "history.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL UNIQUE,
    prompt      TEXT,
    model       TEXT,
    task        TEXT,
    duration    INTEGER,
    aspect_ratio TEXT,
    created_at  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history (created_at DESC);
"""


def init_db() -> None:
    """Create the DB file and schema if they don't already exist."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_CREATE_SQL)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def save_entry(
    filename: str,
    prompt: str | None = None,
    model: str | None = None,
    task: str | None = None,
    duration: int | None = None,
    aspect_ratio: str | None = None,
    created_at: float | None = None,
) -> dict[str, Any]:
    """Insert or replace a history entry; returns the saved row as a dict."""
    ts = created_at or time.time()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO history (filename, prompt, model, task, duration, aspect_ratio, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                prompt       = excluded.prompt,
                model        = excluded.model,
                task         = excluded.task,
                duration     = excluded.duration,
                aspect_ratio = excluded.aspect_ratio,
                created_at   = excluded.created_at
            """,
            (filename, prompt, model, task, duration, aspect_ratio, ts),
        )
    return {
        "filename": filename,
        "prompt": prompt,
        "model": model,
        "task": task,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "created_at": ts,
        "url": f"/exports/{filename}",
    }


def list_entries(limit: int = 100) -> list[dict[str, Any]]:
    """Return history entries, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM history ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for row in rows:
        entry = dict(row)
        entry["url"] = f"/exports/{entry['filename']}"
        # Only include entries whose file still exists on disk
        exports_dir = Path(__file__).resolve().parents[3] / "exports"
        if (exports_dir / entry["filename"]).exists():
            result.append(entry)
    return result

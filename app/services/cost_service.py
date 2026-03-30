"""
cost_service.py — SQLite-backed cost tracking for all generation jobs.

Records each job's actual Veo cost (USD) and provides daily/model breakdowns
for the dashboard. Uses the same DB file as history_service.
"""
import sqlite3
import time
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "history.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS cost_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type    TEXT NOT NULL,
    model       TEXT NOT NULL,
    seconds     REAL NOT NULL,
    cost_usd    REAL NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cost_log_created_at ON cost_log (created_at DESC);
"""


def init_cost_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_CREATE_SQL)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def record_cost(
    job_type: str,
    model: str,
    seconds: float,
    cost_usd: float,
    created_at: float | None = None,
) -> None:
    """Insert one cost record. job_type = 'single' | 'whatif'."""
    ts = created_at or time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO cost_log (job_type, model, seconds, cost_usd, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (job_type, model, seconds, cost_usd, ts),
        )


def get_stats(days: int = 30) -> dict[str, Any]:
    """Return cost summary for the last `days` calendar days."""
    cutoff = time.time() - days * 86400
    with _connect() as conn:
        # All-time totals
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) as total_usd, COUNT(*) as total_jobs "
            "FROM cost_log"
        ).fetchone()
        total_usd = round(float(row["total_usd"]), 4)
        total_jobs = int(row["total_jobs"])

        # By day (within window)
        day_rows = conn.execute(
            """
            SELECT
                date(created_at, 'unixepoch', 'localtime') AS day,
                ROUND(SUM(cost_usd), 4) AS cost_usd,
                COUNT(*) AS job_count
            FROM cost_log
            WHERE created_at >= ?
            GROUP BY day
            ORDER BY day DESC
            """,
            (cutoff,),
        ).fetchall()

        # By model (within window)
        model_rows = conn.execute(
            """
            SELECT
                model,
                ROUND(SUM(cost_usd), 4) AS cost_usd,
                COUNT(*) AS job_count
            FROM cost_log
            WHERE created_at >= ?
            GROUP BY model
            ORDER BY cost_usd DESC
            """,
            (cutoff,),
        ).fetchall()

        # By type (within window)
        type_rows = conn.execute(
            """
            SELECT
                job_type,
                ROUND(SUM(cost_usd), 4) AS cost_usd,
                COUNT(*) AS job_count
            FROM cost_log
            WHERE created_at >= ?
            GROUP BY job_type
            ORDER BY cost_usd DESC
            """,
            (cutoff,),
        ).fetchall()

    return {
        "total_usd": total_usd,
        "total_jobs": total_jobs,
        "window_days": days,
        "by_day": [dict(r) for r in day_rows],
        "by_model": [dict(r) for r in model_rows],
        "by_type": [dict(r) for r in type_rows],
    }

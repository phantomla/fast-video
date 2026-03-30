@echo off
setlocal EnableDelayedExpansion
title fast-video — Server

REM ── Sanity checks ─────────────────────────────────────────────
if not exist .venv (
    echo [ERROR] Virtual environment not found.
    echo         Please run install_windows.bat first.
    pause
    exit /b 1
)

if not exist requirements.txt (
    echo [ERROR] requirements.txt not found.
    echo         Are you running this from the fast-video project folder?
    pause
    exit /b 1
)

REM ── Activate venv ─────────────────────────────────────────────
call .venv\Scripts\activate.bat

REM ── Check required env vars ───────────────────────────────────
if "%VERTEX_AI_CREDENTIALS_FILE%"=="" (
    echo [WARN] VERTEX_AI_CREDENTIALS_FILE is not set.
    echo        Set it to your GCP service account JSON path, e.g.:
    echo          set VERTEX_AI_CREDENTIALS_FILE=C:\keys\vertex-ai.json
    echo.
)
if "%GCP_PROJECT%"=="" (
    echo [WARN] GCP_PROJECT is not set.
    echo        Set it to your GCP project ID, e.g.:
    echo          set GCP_PROJECT=my-gcp-project
    echo.
)

REM ── Ensure output dirs exist ──────────────────────────────────
if not exist exports mkdir exports
if not exist temp\whatif_jobs mkdir temp\whatif_jobs

REM ── Start server ──────────────────────────────────────────────
echo ============================================================
echo  fast-video server starting on http://localhost:8000
echo  Press Ctrl+C to stop
echo ============================================================
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8000

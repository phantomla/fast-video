@echo off
setlocal EnableDelayedExpansion
title fast-video — Install

echo ============================================================
echo  fast-video — Windows Setup
echo ============================================================
echo.

REM ── 1. Check for Python 3.11+ ────────────────────────────────
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 goto :install_python

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 goto :install_python
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 goto :install_python

echo [OK] Python %PY_VER% found.
goto :after_python

:install_python
echo [INFO] Python 3.11 not found. Installing via winget...
winget --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] winget is not available on this machine.
    echo         Please install Python 3.11 manually from:
    echo         https://www.python.org/downloads/
    echo         Then re-run this script.
    pause
    exit /b 1
)
winget install --id Python.Python.3.11 --source winget --silent --accept-package-agreements --accept-source-agreements
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Python via winget.
    echo         Please install Python 3.11 manually from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 3.11 installed. Refreshing PATH...
REM Refresh PATH so the new python is available in this session
for /f "usebackq tokens=2*" %%A in (`reg query "HKCU\Environment" /v PATH 2^>nul`) do set USER_PATH=%%B
for /f "usebackq tokens=2*" %%A in (`reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul`) do set SYS_PATH=%%B
set PATH=%USER_PATH%;%SYS_PATH%

:after_python

REM ── 2. Check for ffmpeg ───────────────────────────────────────
ffmpeg -version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] ffmpeg not found. Installing via winget...
    winget install --id Gyan.FFmpeg --source winget --silent --accept-package-agreements --accept-source-agreements
    if %ERRORLEVEL% NEQ 0 (
        echo [WARN] Could not auto-install ffmpeg.
        echo        Please install manually: https://ffmpeg.org/download.html
        echo        Then add ffmpeg\bin to your PATH.
    ) else (
        echo [OK] ffmpeg installed.
    )
) else (
    echo [OK] ffmpeg found.
)

REM ── 3. Create virtual environment ────────────────────────────
echo.
echo [INFO] Creating virtual environment in .venv ...
if exist .venv (
    echo [INFO] .venv already exists, skipping creation.
) else (
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)

REM ── 4. Install dependencies ───────────────────────────────────
echo.
echo [INFO] Installing Python dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed. Check requirements.txt and your internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

REM ── 5. Create required directories ───────────────────────────
if not exist exports mkdir exports
if not exist temp\whatif_jobs mkdir temp\whatif_jobs
echo [OK] Output directories ready.

REM ── 6. Check for credentials file ────────────────────────────
echo.
echo ============================================================
echo  Setup complete!
echo ============================================================
echo.
echo Before running, make sure you have set these environment variables:
echo.
echo   VERTEX_AI_CREDENTIALS_FILE  = path to your GCP service account JSON
echo   GCP_PROJECT                 = your GCP project ID
echo.
echo You can set them permanently via:
echo   System Properties ^> Advanced ^> Environment Variables
echo.
echo Or create a .env file in this folder (loaded automatically by the app).
echo.
echo Run the server with:   run_windows.bat
echo.
pause

@echo off
setlocal enabledelayedexpansion
title JARVIS Setup
cd /d "%~dp0"

echo ============================================
echo   Starting JARVIS...
echo   Keep this window open. Two more windows
echo   will appear for the backend and frontend -
echo   leave those open too while you use JARVIS.
echo ============================================
echo.

REM ── Check Python ─────────────────────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Attempting to install it...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo.
        echo Could not auto-install Python ^(winget not available^).
        echo Please install it manually from https://www.python.org/downloads/
        echo During setup, make sure to check "Add python.exe to PATH".
        echo Then re-run this file.
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12
    echo.
    echo Python was just installed. Please close this window, open a
    echo NEW one, and double-click start-jarvis.bat again so Windows
    echo picks up the change.
    pause
    exit /b 0
)

REM ── Check Node.js ─────────────────────────────────────────────
where node >nul 2>nul
if errorlevel 1 (
    echo Node.js not found. Attempting to install it...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo.
        echo Could not auto-install Node.js ^(winget not available^).
        echo Please install it manually from https://nodejs.org/ ^(LTS version^)
        echo Then re-run this file.
        pause
        exit /b 1
    )
    winget install -e --id OpenJS.NodeJS.LTS
    echo.
    echo Node.js was just installed. Please close this window, open a
    echo NEW one, and double-click start-jarvis.bat again so Windows
    echo picks up the change.
    pause
    exit /b 0
)

REM ── Check ffmpeg (optional - only needed for video features) ──
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo NOTE: ffmpeg was not found. Subtitles/silence-removal/highlight
    echo features won't work until it's installed. Everything else
    echo ^(including TV control^) will still work fine.
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo Installing ffmpeg...
        winget install -e --id Gyan.FFmpeg
    )
    echo.
)

REM ── Backend setup ────────────────────────────────────────────
echo Setting up the backend...
cd backend
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if not exist .env (
    echo No .env found - copying the example. You'll need to add real API keys.
    copy .env.example .env >nul
)
cd ..

REM ── Frontend setup ───────────────────────────────────────────
echo Setting up the frontend ^(this can take a minute the first time^)...
cd frontend
if not exist node_modules (
    call npm install
)
cd ..

REM ── Launch both servers ──────────────────────────────────────
echo.
echo Launching JARVIS...
start "JARVIS Backend" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "JARVIS Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Waiting for JARVIS to finish starting...
timeout /t 8 /nobreak >nul
start "" "http://localhost:3000"

echo.
echo JARVIS should now be open in your browser.
echo To stop JARVIS, just close the two other windows that opened.
echo You can close this window now.
pause

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
if errorlevel 1 (
    echo.
    echo Backend dependency install failed - see the error above.
    echo Common cause: no internet connection during setup.
    pause
    exit /b 1
)
if not exist .env (
    echo No .env found - copying the example. You'll need to add real API keys.
    copy .env.example .env >nul
)
cd ..

REM ── Frontend setup ───────────────────────────────────────────
REM Always run this (not just when node_modules is missing) - it's fast
REM when nothing changed, and this avoids treating a previous *failed*
REM install as if it had succeeded.
echo Setting up the frontend ^(this can take a minute the first time^)...
cd frontend
call npm install
if errorlevel 1 (
    echo.
    echo Frontend dependency install failed - see the error above.
    echo Common causes: no internet connection, or antivirus blocking npm.
    pause
    exit /b 1
)
cd ..

REM ── Launch both servers ──────────────────────────────────────
echo.
echo Launching JARVIS...
start "JARVIS Backend" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "JARVIS Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Waiting for JARVIS to finish starting - this can take up to a minute...
set READY=0
for /l %%i in (1,1,30) do (
    if !READY! == 0 (
        timeout /t 2 /nobreak >nul
        powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri http://localhost:3000 -UseBasicParsing -TimeoutSec 2) | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
        if not errorlevel 1 set READY=1
    )
)

if !READY! == 0 (
    echo.
    echo JARVIS is taking longer than expected to start.
    echo Check the "JARVIS Backend" and "JARVIS Frontend" windows for red
    echo error text - that will show what went wrong. Once you see
    echo "Ready" in the Frontend window, open http://localhost:3000 yourself.
    pause
    exit /b 1
)

start "" "http://localhost:3000"
echo.
echo JARVIS should now be open in your browser.
echo To stop JARVIS, just close the two other windows that opened.
echo You can close this window now.
pause

@echo off
title FIGHT IQ Launcher (DEMO sandbox)

echo Starting FIGHT IQ in DEMO mode...
echo This uses an ISOLATED sandbox database (data\app.demo.db), seeded from prod on
echo first run. Your real prod data (data\app.db) and your friends' accounts/picks are
echo NOT touched. Delete data\app.demo.db to re-seed a fresh sandbox from prod.
echo.

REM Move to this script's folder
cd /d "%~dp0"

echo Starting backend (DEMO)...
start "FIGHT IQ Backend (DEMO)" cmd /k "cd /d backend && call .venv\Scripts\activate && set "FIGHTIQ_DEMO=1" && uvicorn app.main:app --reload"

echo Starting frontend...
start "FIGHT IQ Frontend" cmd /k "cd /d frontend && npm run dev"

echo.
echo Backend (DEMO) at: http://127.0.0.1:8000/docs
echo Frontend at:       http://localhost:5173/
echo The top bar will show a "Sandbox DB" pill so you know you're in demo mode.
echo.

pause

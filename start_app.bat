@echo off
title UFC Predictor Launcher

echo Starting UFC Fight Predictor...
echo.

REM Move to this script's folder
cd /d "%~dp0"

echo Starting backend...
start "UFC Predictor Backend" cmd /k "cd /d backend && call .venv\Scripts\activate && uvicorn app.main:app --reload"

echo Starting frontend...
start "UFC Predictor Frontend" cmd /k "cd /d frontend && npm run dev"

echo.
echo Backend should open at:
echo http://127.0.0.1:8000/docs
echo.
echo Frontend should open at:
echo http://localhost:5173/
echo.
echo If the browser does not open automatically, copy the frontend URL above.
echo.

pause
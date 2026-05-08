@echo off
title S.I.R.S — Smart Incident Response System
color 0B
echo.
echo  ███████╗    ██╗     ██████╗     ███████╗
echo  ██╔════╝    ██║     ██╔══██╗    ██╔════╝
echo  ███████╗    ██║     ██████╔╝    ███████╗
echo  ╚════██║    ██║     ██╔══██╗    ╚════██║
echo  ███████║    ██║     ██║  ██║    ███████║
echo  ╚══════╝    ╚═╝     ╚═╝  ╚═╝    ╚══════╝
echo.
echo  Smart Incident Response System v1.1
echo  Multi-Agent Local-AI Platform for Smart Cities
echo  ==========================================
echo.

:: Check Python
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies...
cd /d "%~dp0backend"
py -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Dependencies installed successfully!
echo [3/3] Starting S.I.R.S Backend Server...
echo.
echo  Server URL: http://localhost:8000
echo  API Docs:   http://localhost:8000/docs
echo  Dashboard:  http://localhost:8000/dashboard.html
echo  Judges:     http://localhost:8000/judges.html
echo.
echo  Local AI:   Ollama only - recommended model: qwen3:8b
echo  To enable local AI, run in another terminal: ollama serve
echo  Install model once: ollama pull qwen3:8b
echo.
echo  Press Ctrl+C to stop the server
echo  ==========================================
echo.

:: Open browser after 2 seconds
start "" timeout /t 2 /nobreak >nul & start "" "http://localhost:8000"

:: Start server
py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause

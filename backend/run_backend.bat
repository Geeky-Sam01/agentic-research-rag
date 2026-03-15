@echo off
setlocal
echo ==========================================
echo   Starting Agentic Research RAG Backend
echo ==========================================

:: Change to the script's directory
cd /d "%~dp0"

:: Check for .venv
if not exist ".venv" (
    echo [ERROR] Virtual environment (.venv) not found!
    echo Please create it first using: uv venv
    pause
    exit /b
)

:: Attempt to kill existing process on port 8000
echo Checking for existing processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    if not "%%a"=="" (
        echo Killing process PID %%a holding port 8000...
        taskkill /F /PID %%a
    )
)

echo [1/2] Activating virtual environment...
call .venv\Scripts\activate

echo [2/2] Starting Uvicorn server...
echo URL: http://127.0.0.1:8000
echo Docs: http://127.0.0.1:8000/docs
echo.

:: Use 'python -m uvicorn' to ensure it uses the venv's python
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause

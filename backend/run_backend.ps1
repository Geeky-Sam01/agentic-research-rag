Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Starting Agentic Research RAG Backend" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Change to the script's directory
Set-Location $PSScriptRoot

# Check for .venv
if (-Not (Test-Path ".venv")) {
    Write-Host "[ERROR] Virtual environment (.venv) not found!" -ForegroundColor Red
    Write-Host "Please create it first using: uv venv"
    Read-Host "Press Enter to exit"
    exit
}

# Kill existing process on 8000
Write-Host "Checking for existing processes on port 8000..." -ForegroundColor Gray
$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($connections) {
    foreach ($conn in $connections) {
        Write-Host "Killing process PID $($conn.OwningProcess) holding port 8000..." -ForegroundColor Yellow
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "[1/2] Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

Write-Host "[2/2] Starting Uvicorn server..." -ForegroundColor Yellow
Write-Host "URL: http://127.0.0.1:8000"
Write-Host "Docs: http://127.0.0.1:8000/docs"
Write-Host ""

# Run using the python from the venv
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Starting Agentic Research RAG Backend" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Change to the script's directory
Set-Location $PSScriptRoot

# Kill existing process on 8000 (Simplified)
Write-Host "Checking for existing processes on port 8000..." -ForegroundColor Gray
$proc = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
if ($proc) {
    Write-Host "Killing process PID $proc holding port 8000..." -ForegroundColor Yellow
    Stop-Process -Id $proc -Force -ErrorAction SilentlyContinue
}

# The UV way: 'uv run' automatically syncs dependencies and uses the correct venv
Write-Host "[1/1] Syncing environment and starting Uvicorn..." -ForegroundColor Yellow
Write-Host "URL: http://127.0.0.1:8000"
Write-Host "Docs: http://127.0.0.1:8000/docs"
Write-Host ""

# uv run ensures pyproject.toml is satisfied before running uvicorn
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

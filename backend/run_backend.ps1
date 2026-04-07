Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Starting Agentic Research RAG Backend" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan


Set-Location $PSScriptRoot


Write-Host "Checking for existing processes on port 8000..." -ForegroundColor Gray
$proc = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
if ($proc) {
    Write-Host "Killing process PID $proc holding port 8000..." -ForegroundColor Yellow
    Stop-Process -Id $proc -Force -ErrorAction SilentlyContinue
}


Write-Host "[1/1] Syncing environment and starting Uvicorn..." -ForegroundColor Yellow
Write-Host "URL: http://127.0.0.1:8000"
Write-Host "Docs: http://127.0.0.1:8000/docs"
Write-Host ""


uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

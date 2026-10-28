# Run inside the extracted project root, from Windows PowerShell:
# powershell -ExecutionPolicy Bypass -File .\start_pitch_demo.ps1
# Local synthetic demo only. Does not connect CIPC, AVS, Ozow or WhatsApp.
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host 'No virtual environment found; first run: py -3 -m venv .venv' -ForegroundColor Yellow
    exit 1
}
& $python -m scripts.seed_pitch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Ready. Visit http://127.0.0.1:8000, log in as the demo owner, then open /pitch' -ForegroundColor Green
& $python -m uvicorn fraudfence.main:app --reload

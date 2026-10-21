$Root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$py = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Virtualenv missing. Run .\install.ps1 first." -ForegroundColor Red
    exit 1
}
Set-Location (Join-Path $Root "backend")
Write-Host "Starting FreeAgent IDE at http://127.0.0.1:8765" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop."
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8765

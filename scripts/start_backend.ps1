# Start FastAPI backend on Windows
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Py)) { Write-Host '[ERROR] .venv missing'; exit 1 }
Get-NetTCPConnection -LocalPort 8900 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
$env:PYTHONPATH = $Root
Start-Process -FilePath $Py -ArgumentList '-m','uvicorn','security_agent.api.app:app','--host','127.0.0.1','--port','8900' -WorkingDirectory $Root -WindowStyle Hidden
Start-Sleep -Seconds 3
try {
  $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8900/api/health' -TimeoutSec 5
  Write-Host "[OK] backend v$($h.version)"
  Write-Host 'http://127.0.0.1:8900/ admin/admin123'
} catch { Write-Host '[FAIL] backend not up'; exit 1 }

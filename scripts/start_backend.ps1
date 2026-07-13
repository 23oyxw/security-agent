# Start FastAPI backend on Windows
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Py)) { Write-Host '[ERROR] .venv missing'; exit 1 }
# Free port 8900 — include uvicorn reloader orphans (parent PID dead, child still listening)
Get-NetTCPConnection -LocalPort 8900 -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'uvicorn|security_agent\.api|multiprocessing\.spawn' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
$env:PYTHONPATH = $Root
Start-Process -FilePath $Py -ArgumentList '-m','uvicorn','security_agent.api.app:app','--host','127.0.0.1','--port','8900' -WorkingDirectory $Root -WindowStyle Hidden
Start-Sleep -Seconds 3
try {
  $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8900/api/health' -TimeoutSec 5
  Write-Host "[OK] backend v$($h.version)"
  # 冒烟：编排接口必须可用，否则智能助手无回复
  $login = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8900/api/auth/login' -ContentType 'application/json' -Body '{"username":"admin","password":"admin123"}' -TimeoutSec 10
  $tok = $login.access_token
  $hdr = @{ Authorization = "Bearer $tok" }
  $null = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8900/api/agent/orchestrate' -Headers $hdr -ContentType 'application/json' -Body '{"message":"health ping"}' -TimeoutSec 60
  Write-Host '[OK] agent orchestrate'
  Write-Host 'http://127.0.0.1:8900/ admin/admin123'
} catch {
  Write-Host "[FAIL] backend or orchestrate: $($_.Exception.Message)"
  exit 1
}

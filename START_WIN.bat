@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Run first:
  echo   py -3.10 -m venv .venv
  echo   .venv\Scripts\activate
  echo   pip install -i https://mirrors.aliyun.com/pypi/simple -e .
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" copy /y ".env.example" ".env" >nul
  echo [WARN] Edit .env and set LLM_API_KEY, then run this again.
  notepad .env
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo [ERROR] frontend\dist missing. Build frontend first:
  echo   cd frontend
  echo   npm install --legacy-peer-deps
  echo   npm run build
  pause
  exit /b 1
)

if not exist "data\logs" mkdir "data\logs"

rem Free port 8900 if stuck
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8900" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
echo Starting http://127.0.0.1:8900/
echo Login: admin / admin123
echo If pages empty: use 8900 NOT file:// dist
echo Press Ctrl+C to stop.

rem Start server in background, wait for health, then open browser
start "security-agent-api" /min cmd /c ""%CD%\.venv\Scripts\python.exe" -m uvicorn security_agent.api.app:app --host 127.0.0.1 --port 8900"

set /a _tries=0
:wait_health
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8900/api/health' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto open_browser
set /a _tries+=1
if %_tries% geq 30 (
  echo [ERROR] Backend did not start within 30s. Check data\logs or run in foreground:
  echo   .venv\Scripts\python.exe -m uvicorn security_agent.api.app:app --host 127.0.0.1 --port 8900
  pause
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_health

:open_browser
echo [OK] Backend ready.
start "" "http://127.0.0.1:8900/"
echo Backend running in minimized window "security-agent-api". Close it to stop.
pause

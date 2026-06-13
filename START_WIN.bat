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

set PYTHONPATH=.
echo Starting http://127.0.0.1:8900/
echo Login: admin / admin123
echo Press Ctrl+C to stop.
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" http://127.0.0.1:8900/
".venv\Scripts\python.exe" -m uvicorn security_agent.api.app:app --host 127.0.0.1 --port 8900

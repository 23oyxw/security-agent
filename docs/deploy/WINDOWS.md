# Windows 运行说明（规范正文）

> 根目录 WINDOWS_GUIDE_CN.txt / WINDOWS_RUN_GUIDE.txt 为本文件副本。

## 中文版

`	ext
﻿================================================================================
  security-agent Windows 运行说明 (中文版)
  版本 0.9.0
================================================================================

【发给老师的文件】
  整个 security-agent 文件夹（含 frontend/dist）
  可打 zip，附带本说明

【需安装】Python 3.10 + Node.js 18+（重建前端时用）+ 浏览器

【启动步骤 - 每条单独回车】

1. cd C:\路径\security-agent
2. py -3.10 -m venv .venv
3. .venv\Scripts\activate
4. pip install -i https://mirrors.aliyun.com/pypi/simple -e .
5. copy .env.example .env
6. notepad .env   (填 LLM_API_KEY 等)
7. 若白屏: cd frontend && npm install --legacy-peer-deps && npm run build && cd ..
8. set PYTHONPATH=.
9. mkdir data\logs 2>nul
10. .venv\Scripts\python -m uvicorn security_agent.api.app:app --host 127.0.0.1 --port 8900
11. 浏览器 http://localhost:8900/  Ctrl+F5
12. 登录 admin / admin123

【Python 依赖】
fastapi uvicorn python-multipart PyJWT passlib python-dotenv httpx pyyaml
slowapi tenacity websockets openai mcp psutil
(可选: streamlit pandas numpy matplotlib plotly)

【常见问题】
- encodings 错误 -> 用 py -3.10
- 白屏 -> npm run build 重建 frontend/dist
- 命令语法错 -> 不要多条粘一行

【一键启动】完成上述安装后，可双击 START_WIN.bat

访问: http://localhost:8900/

`

## English

`	ext
================================================================================
  security-agent - Windows Run Guide (B/S mode, port 8900)
  Version: 0.9.0
================================================================================

[1] Required software on teacher's PC

  - Python 3.10 or 3.11 (recommended: 3.10)
    Download: https://www.python.org/downloads/
    Check "Add Python to PATH" during install.

  - Node.js 18+ (only needed if frontend/dist is missing or white screen)
    Download: https://nodejs.org/

  - Browser: Chrome or Edge

[2] What to send to teacher

  Send the whole project folder "security-agent", including:
    - security_agent/          (backend)
    - frontend/dist/           (built frontend - MUST be complete)
    - pyproject.toml
    - .env.example
    - this file WINDOWS_RUN_GUIDE.txt

  Do NOT send only .py files. frontend/dist must be included.

[3] Quick check (optional)

  Open CMD, run one command per line:

    py -0p

  You should see Python 3.10 or 3.11.

  If "python" shows encodings error, always use "py -3.10", not bare "python".

    node --version

  Should be v18 or higher.

[4] Install and start - ONE COMMAND PER LINE (do not paste all together)

  Step 1 - go to project folder:

    cd C:\path\to\security-agent

  Step 2 - create virtual env:

    py -3.10 -m venv .venv

  Step 3 - activate venv:

    .venv\Scripts\activate

  You should see (.venv) in the prompt.

  Step 4 - install Python packages:

    pip install -i https://mirrors.aliyun.com/pypi/simple -e .

  If -e . fails, run:

    pip install -i https://mirrors.aliyun.com/pypi/simple httpx mcp openai pandas numpy matplotlib pillow plotly psutil python-dotenv streamlit fastapi uvicorn python-multipart PyJWT passlib[bcrypt] websockets pyyaml slowapi tenacity

  Step 5 - copy config:

    copy .env.example .env

  Step 6 - edit .env:

    notepad .env

  Minimum settings for DeepSeek (example):

    USE_LITELLM_PROXY=false
    LLM_API_KEY=your_deepseek_api_key_here
    LLM_BASE_URL=https://api.deepseek.com/v1
    LLM_MODEL=deepseek-chat
    RAG_USE_EMBEDDINGS=false

  Save and close notepad.

  Step 7 - rebuild frontend (required if page is white/blank):

    cd frontend

    npm install --legacy-peer-deps

    npm run build

    cd ..

  Step 8 - set module path:

    set PYTHONPATH=.

  Step 9 - create log folder:

    mkdir data\logs 2>nul

  Step 10 - start backend:

    .venv\Scripts\python -m uvicorn security_agent.api.app:app --host 127.0.0.1 --port 8900

  Wait for: Uvicorn running on http://127.0.0.1:8900
  Keep this window open.

  Step 11 - open browser:

    http://localhost:8900/

  Press Ctrl+F5 to hard refresh.

  Step 12 - login:

    username: admin
    password: admin123

[5] Python dependencies (from pyproject.toml)

  Core (required for答辩 B/S):
    fastapi, uvicorn, python-multipart, PyJWT, passlib[bcrypt]
    python-dotenv, httpx, pyyaml, slowapi, tenacity, websockets
    openai, mcp, psutil

  Optional (old Streamlit
`

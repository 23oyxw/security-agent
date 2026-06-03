#!/usr/bin/env bash
# 重启 FastAPI（加载最新代码，监听 0.0.0.0:8900）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p data/logs

if [[ -f data/.api.pid ]]; then
  pid="$(cat data/.api.pid 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    sleep 1
  fi
fi
pkill -f "uvicorn security_agent.api.app:app" 2>/dev/null || true
sleep 1

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  echo "缺少 .venv，请先 uv sync"
  exit 1
fi

export PYTHONPATH="${ROOT}"
export SEC_API_HOST="${SEC_API_HOST:-0.0.0.0}"
export SEC_API_PORT="${SEC_API_PORT:-8900}"

nohup "${PY}" -m uvicorn security_agent.api.app:app \
  --host "${SEC_API_HOST}" \
  --port "${SEC_API_PORT}" \
  --log-level info \
  >>data/logs/api.log 2>&1 &
echo $! >data/.api.pid
sleep 2

if curl -sf "http://127.0.0.1:${SEC_API_PORT}/api/health" >/dev/null; then
  echo "✅ API 已重启 → http://${SEC_API_HOST}:${SEC_API_PORT}/"
  echo "   文档: http://127.0.0.1:${SEC_API_PORT}/docs"
else
  echo "❌ 启动失败，查看 data/logs/api.log"
  tail -20 data/logs/api.log
  exit 1
fi

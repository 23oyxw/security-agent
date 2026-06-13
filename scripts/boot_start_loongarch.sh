#!/usr/bin/env bash
# LoongArch/Kylin 启动 B/S（FastAPI :8900，pip + PYTHONPATH，不依赖 uv）
set -euo pipefail

SEC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SEC_ROOT}/.env"
LOG_DIR="${SEC_ROOT}/data/logs"
API_PID_FILE="${SEC_ROOT}/data/.api.pid"
API_PORT="${SEC_API_PORT:-8900}"
API_HOST="${SEC_API_HOST:-0.0.0.0}"

log() { echo "[boot_start_loongarch] $*"; }

cd "${SEC_ROOT}"
find . -name '*.sh' -exec sed -i 's/\r$//' {} + 2>/dev/null || true
mkdir -p "${LOG_DIR}"

if [[ ! -d .venv ]]; then
  log "未找到 .venv，请先: bash scripts/bootstrap-kylin-loongarch-pip.sh"
  exit 1
fi

PY="${SEC_ROOT}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
  log ".venv/bin/python 不可用" >&2
  exit 1
fi

if [[ -f "${API_PID_FILE}" ]]; then
  old_pid="$(cat "${API_PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
    log "停止旧进程 PID=${old_pid}"
    kill "${old_pid}" 2>/dev/null || true
    sleep 1
  fi
fi
pkill -f "uvicorn security_agent.api.app:app" 2>/dev/null || true

export PYTHONPATH="${SEC_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
log "启动 API http://${API_HOST}:${API_PORT} ..."
nohup "${PY}" -m uvicorn security_agent.api.app:app \
  --host "${API_HOST}" --port "${API_PORT}" \
  >>"${LOG_DIR}/api.log" 2>&1 &
echo $! >"${API_PID_FILE}"
sleep 2

if curl -sf "http://127.0.0.1:${API_PORT}/api/health" >/dev/null 2>&1; then
  log "健康检查通过"
else
  log "启动中或失败，查看: tail -f ${LOG_DIR}/api.log"
fi

log "浏览器: http://<主机IP>:${API_PORT}/"
log "停止: pkill -f 'uvicorn security_agent.api.app'"

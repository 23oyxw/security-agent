#!/usr/bin/env bash
#==============================================================================
# 停止安全运维 Agent 所有服务（FastAPI + Streamlit + LiteLLM）
#==============================================================================

set -euo pipefail

SEC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PID_FILE="${SEC_ROOT}/data/.api.pid"
STREAMLIT_PID_FILE="${SEC_ROOT}/data/.streamlit.pid"
LITELLM_PID_FILE="${SEC_ROOT}/data/.litellm.pid"
FRONTEND_PID_FILE="${SEC_ROOT}/data/.frontend-dev.pid"
API_PORT="${SEC_API_PORT:-8900}"
STREAMLIT_PORT="${SEC_UI_PORT:-8501}"

log() { echo "[boot_stop] $*"; }
stopped=0

#------------------------------------------------------------------------------
# 停止 FastAPI 后端
#------------------------------------------------------------------------------
if [[ -f "${API_PID_FILE}" ]]; then
  pid="$(cat "${API_PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill -TERM "${pid}" 2>/dev/null && log "已停止 FastAPI (PID ${pid})" && stopped=1
    sleep 1
    kill -KILL "${pid}" 2>/dev/null || true
  fi
  rm -f "${API_PID_FILE}"
fi

# 兜底：杀掉占用 API 端口的进程
if command -v fuser &>/dev/null; then
  fuser -k "${API_PORT}/tcp" 2>/dev/null && stopped=1 || true
fi

#------------------------------------------------------------------------------
# 停止 Vue dev server
#------------------------------------------------------------------------------
if [[ -f "${FRONTEND_PID_FILE}" ]]; then
  pid="$(cat "${FRONTEND_PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill -TERM "${pid}" 2>/dev/null && log "已停止 Vue dev server (PID ${pid})" && stopped=1
  fi
  rm -f "${FRONTEND_PID_FILE}"
fi

#------------------------------------------------------------------------------
# 停止 LiteLLM Docker 容器
#------------------------------------------------------------------------------
if docker ps --filter name=security-agent-litellm --format "{{.ID}}" 2>/dev/null | grep -q .; then
  log "停止 LiteLLM Docker 容器..."
  docker rm -f security-agent-litellm 2>/dev/null && log "LiteLLM 容器已停止" && stopped=1
  rm -f "${LITELLM_PID_FILE}"
fi

#------------------------------------------------------------------------------
# 停止 Streamlit
#------------------------------------------------------------------------------
if [[ -f "${STREAMLIT_PID_FILE}" ]]; then
  pid="$(cat "${STREAMLIT_PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill -TERM "${pid}" 2>/dev/null && log "已停止 Streamlit (PID ${pid})" && stopped=1
    sleep 1
    kill -KILL "${pid}" 2>/dev/null || true
  fi
  rm -f "${STREAMLIT_PID_FILE}"
fi

# 兜底：杀掉占用 Streamlit 端口的进程
if command -v fuser &>/dev/null; then
  fuser -k "${STREAMLIT_PORT}/tcp" 2>/dev/null && stopped=1 || true
fi

#------------------------------------------------------------------------------
# 结果
#------------------------------------------------------------------------------
if [[ "${stopped}" -eq 1 ]]; then
  log "所有服务已停止"
else
  log "未发现运行中的服务"
fi
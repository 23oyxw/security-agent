#!/bin/bash
#==============================================================================
# 一键启动 — 安全运维 Agent（FastAPI + Vue 控制台）
#
# 用法:
#   bash start.sh              # 生产模式（:8900）
#   bash start.sh --dev        # 开发模式（:5173 前端）
#   bash start.sh --streamlit  # 额外启动 Streamlit 旧版 (:8501)
#
# 停止: bash stop.sh  或  bash boot_stop.sh
#==============================================================================
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

log() { echo "[start] $*"; }

# 首次运行：无 .env 或无 .venv
if [[ ! -f "${ROOT}/.env" ]] || [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  if [[ -f "${ROOT}/scripts/bootstrap-kylin-loongarch.sh" ]]; then
    log "首次运行，正在初始化环境..."
    bash "${ROOT}/scripts/bootstrap-kylin-loongarch.sh"
  elif [[ -f "${ROOT}/.env.example" && ! -f "${ROOT}/.env" ]]; then
    cp "${ROOT}/.env.example" "${ROOT}/.env"
    log "已生成 .env，请填写 LLM_API_KEY 后重新执行 bash start.sh"
    exit 1
  fi
fi

if [[ -f "${ROOT}/.env" ]] && ! grep -qE '^LLM_API_KEY=.+' "${ROOT}/.env" 2>/dev/null; then
  if grep -q 'your_mimo_key' "${ROOT}/.env" 2>/dev/null; then
    log "⚠️  请编辑 .env 中的 LLM_API_KEY 后再启动"
  fi
fi

bash "${ROOT}/boot_start.sh" "$@"

PORT="${SEC_API_PORT:-8900}"
HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
[[ -z "${HOST_IP}" ]] && HOST_IP="127.0.0.1"

echo ""
log "========================================="
log "  快捷访问"
log "  本机:   http://127.0.0.1:${PORT}/"
log "  局域网: http://${HOST_IP}:${PORT}/"
log "  停止:   bash stop.sh"
log "========================================="

#!/usr/bin/env bash
#==============================================================================
# 启动安全运维 Agent — FastAPI 后端 + Vue 前端 (+ 可选 Streamlit 旧版)
#
# 默认端口: API 8900（答辩推荐，与 vite proxy / e2e 一致）
#           文档中若写 8000，请 export SEC_API_PORT=8000 或改本脚本默认值
# 访问:     http://<主机>:8900/  （生产：已构建的 frontend/dist）
#           bash boot_start.sh --dev → http://<主机>:5173/ （proxy → 8900）
#
# 用法: bash boot_start.sh [--dev]
#   --dev        开发模式，启动 Vue dev server 代替构建静态文件
#==============================================================================

set -eu

SEC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SEC_ROOT}/.env"
ENV_EXAMPLE="${SEC_ROOT}/.env.example"
LOG_DIR="${SEC_ROOT}/data/logs"
API_PID_FILE="${SEC_ROOT}/data/.api.pid"
API_PORT="${SEC_API_PORT:-8900}"
API_HOST="${SEC_API_HOST:-0.0.0.0}"
LITELLM_PID_FILE="${SEC_ROOT}/data/.litellm.pid"
LITELLM_LOG="${LOG_DIR}/litellm.log"

# 解析参数
DEV_MODE=false
for arg in "$@"; do
  case "$arg" in
    --dev) DEV_MODE=true ;;
  esac
done

if [[ -x "${HOME}/.local/bin/uv" ]]; then
  UV_BIN="${HOME}/.local/bin/uv"
else
  UV_BIN="$(command -v uv 2>/dev/null || true)"
fi

export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

log() { echo "[boot_start] $*"; }

if [[ -z "${UV_BIN}" || ! -x "${UV_BIN}" ]]; then
  echo "[boot_start] 未找到 uv，请先安装: https://docs.astral.sh/uv/" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}" "${SEC_ROOT}/data/reports"
touch "${SEC_ROOT}/data/audit.log" 2>/dev/null || true

if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${ENV_EXAMPLE}" ]]; then
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
    log "已从 .env.example 生成 .env，请编辑 LLM_API_KEY 后重启"
  else
    touch "${ENV_FILE}"
  fi
fi

cd "${SEC_ROOT}"

# 维护虚拟环境
_venv_broken() {
  [[ ! -d .venv ]] && return 0
  local py
  py="$(readlink -f .venv/bin/python3 2>/dev/null || true)"
  [[ -z "${py}" || ! -x "${py}" ]] && return 0
  if ! "${UV_BIN}" run python -c "import fastapi" &>/dev/null; then
    return 0
  fi
  return 1
}

if _venv_broken; then
  log "虚拟环境需重建..."
  rm -rf .venv
  "${UV_BIN}" sync
else
  "${UV_BIN}" sync -q 2>/dev/null || "${UV_BIN}" sync
fi

#------------------------------------------------------------------------------
# 步骤 1: 启动 LiteLLM 代理（Docker 容器，可选）
#------------------------------------------------------------------------------
_start_litellm() {
  if [[ ! -f "${ENV_FILE}" ]]; then return 0; fi
  if ! grep -q "^USE_LITELLM_PROXY=true" "${ENV_FILE}" 2>/dev/null; then return 0; fi
  if docker ps --filter name=security-agent-litellm --format "{{.Status}}" 2>/dev/null | grep -q Up; then
    log "LiteLLM (Docker) 已在运行"
    return 0
  fi
  local COMPOSE_FILE="${SEC_ROOT}/configs/docker-compose.litellm.yml"
  if [[ -f "${COMPOSE_FILE}" ]]; then
    log "正在通过 docker compose 启动 LiteLLM..."
    docker compose -f "${COMPOSE_FILE}" up -d 2>>"${LITELLM_LOG}" || log "LiteLLM 启动失败（非致命）"
  fi
  for i in $(seq 1 5); do
    if curl -sf http://localhost:4000/health/liveliness >/dev/null 2>&1; then
      log "LiteLLM 健康检查通过"
      return 0
    fi
    sleep 2
  done
  log "⚠️ LiteLLM 未就绪 — AI 功能可能不可用（非致命）"
}

_start_litellm

#------------------------------------------------------------------------------
# 步骤 2: 创建受限用户（权限隔离）
#------------------------------------------------------------------------------
if [[ -f "${SEC_ROOT}/scripts/setup_restricted_user.sh" ]]; then
  log "检查受限用户..."
  bash "${SEC_ROOT}/scripts/setup_restricted_user.sh" 2>/dev/null || log "受限用户创建跳过"
fi

#------------------------------------------------------------------------------
# 步骤 3: 启动 FastAPI 后端
#------------------------------------------------------------------------------
_api_alive() {
  curl -sf -o /dev/null "http://127.0.0.1:${API_PORT}/api/health" 2>/dev/null
}

if _api_alive; then
  log "FastAPI 已在运行 → http://${API_HOST}:${API_PORT}"
else
  # 清理僵尸 PID 文件
  if [[ -f "${API_PID_FILE}" ]]; then
    old_pid="$(cat "${API_PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
      log "PID ${old_pid} 存在但无响应，强制终止..."
      kill "${old_pid}" 2>/dev/null || true
      sleep 1
    fi
    rm -f "${API_PID_FILE}"
  fi

  log "启动 FastAPI 后端 (端口 ${API_PORT})..."
  if [[ -x "${SEC_ROOT}/.venv/bin/python" ]]; then
    UVICORN_CMD=("${SEC_ROOT}/.venv/bin/python" -m uvicorn security_agent.api.app:app)
  else
    UVICORN_CMD=("${UV_BIN}" run uvicorn security_agent.api.app:app)
  fi
  nohup env PYTHONPATH="${SEC_ROOT}" "${UVICORN_CMD[@]}" \
    --host "${API_HOST}" \
    --port "${API_PORT}" \
    --log-level info \
    >>"${LOG_DIR}/api.log" 2>&1 &
  echo $! >"${API_PID_FILE}"

  # 健康检查（最多等 10 秒）
  for i in $(seq 1 10); do
    sleep 1
    if _api_alive; then
      log "✅ FastAPI 已启动 PID $(cat "${API_PID_FILE}") → http://${API_HOST}:${API_PORT}"
      log "   API 文档: http://${API_HOST}:${API_PORT}/docs"
      log "   日志: ${LOG_DIR}/api.log"
      break
    fi
    if ! kill -0 "$(cat "${API_PID_FILE}")" 2>/dev/null; then
      log "❌ FastAPI 进程已退出，请查看: ${LOG_DIR}/api.log"
      tail -30 "${LOG_DIR}/api.log" >&2
      break
    fi
  done
  if ! _api_alive; then
    log "❌ FastAPI 启动超时，请查看: ${LOG_DIR}/api.log"
  fi
fi

#------------------------------------------------------------------------------
# 步骤 4: 构建/启动前端
#------------------------------------------------------------------------------
if [[ "${DEV_MODE}" == true ]]; then
  # 开发模式：启动 Vue dev server
  if [[ -f "${SEC_ROOT}/frontend/package.json" ]]; then
    log "启动 Vue 开发服务器..."
    cd "${SEC_ROOT}/frontend"
    if [[ ! -d node_modules ]]; then
      npm install --prefer-offline >>"${LOG_DIR}/frontend-install.log" 2>&1
    fi
    nohup npx vite --host 0.0.0.0 --port 5173 >>"${LOG_DIR}/frontend-dev.log" 2>&1 &
    echo $! >"${SEC_ROOT}/data/.frontend-dev.pid"
    cd "${SEC_ROOT}"
    log "✅ Vue dev server → http://localhost:5173"
  fi
else
  # 生产模式：dist 缺失 / 资源不完整 / src 比 dist 新 → 必须重新 build
  _frontend_needs_build() {
    local dist="${SEC_ROOT}/frontend/dist"
    local idx="${dist}/index.html"
    [[ ! -f "${idx}" ]] && return 0
    local asset missing=0
    while IFS= read -r asset; do
      [[ -n "${asset}" && -f "${dist}/${asset}" ]] || missing=1
    done < <(grep -oE 'assets/[^"'"'"' ]+' "${idx}" 2>/dev/null || true)
    [[ "${missing}" -eq 1 ]] && return 0
    find "${SEC_ROOT}/frontend/src" -newer "${idx}" -print -quit 2>/dev/null | grep -q . && return 0
    return 1
  }
  if [[ -f "${SEC_ROOT}/frontend/package.json" ]] && _frontend_needs_build; then
    log "构建 Vue 前端（dist 缺失、不完整或源码已更新）..."
    cd "${SEC_ROOT}/frontend"
    if [[ ! -d node_modules ]]; then
      npm install --prefer-offline >>"${LOG_DIR}/frontend-install.log" 2>&1
    fi
    npm run build >>"${LOG_DIR}/frontend-build.log" 2>&1
    cd "${SEC_ROOT}"
    if [[ -d "${SEC_ROOT}/frontend/dist" ]]; then
      log "✅ 前端构建完成"
    else
      log "⚠️ 前端构建失败，请查看: ${LOG_DIR}/frontend-build.log"
    fi
  elif [[ -d "${SEC_ROOT}/frontend/dist" ]]; then
    log "前端 dist 已是最新，跳过构建"
  fi
fi

#------------------------------------------------------------------------------
# 完成
#------------------------------------------------------------------------------
echo ""
log "========================================="
log "  银河麒麟智能安全运维 Agent 已启动"
log "========================================="
log "  Web 控制台: http://${API_HOST}:${API_PORT}"
log "  API 文档:   http://${API_HOST}:${API_PORT}/docs"
log "  停止服务:   bash boot_stop.sh"
log "========================================="
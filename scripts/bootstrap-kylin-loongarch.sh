#!/bin/bash
# 麒麟 V11 Swan25 + LoongArch 实验机首次初始化
# 用法: bash scripts/bootstrap-kylin-loongarch.sh
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# 修复 tar 解压后丢失的执行权限
find . -name '*.sh' -exec chmod +x {} + 2>/dev/null || true

log() { echo "[kylin-bootstrap] $*"; }

ARCH="$(uname -m)"
log "架构: ${ARCH} · 系统: $(grep -E '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2- | tr -d '\"' || uname -s)"

if [[ "${ARCH}" != "loongarch64" && "${ARCH}" != "loong64" ]]; then
  log "提示: 当前非 LoongArch (${ARCH})，脚本仍可继续（开发机自检）"
fi

if [[ -x "${HOME}/.local/bin/uv" ]]; then
  UV="${HOME}/.local/bin/uv"
elif command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
else
  log "未找到 uv，尝试: curl -LsSf https://astral.sh/uv/install.sh | sh"
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV="${HOME}/.local/bin/uv"
  else
    log "请安装 uv 或: sudo dnf install -y python3-pip && pip3 install uv"
    exit 1
  fi
fi

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v dnf >/dev/null 2>&1; then
  log "未检测到 dnf，请手动安装 python3、gcc、nodejs"
else
  log "建议已执行: sudo dnf install -y python3 python3-devel gcc gcc-c++ make git curl nodejs npm"
fi

mkdir -p "${ROOT}/data/logs" "${ROOT}/data/reports"
touch "${ROOT}/data/audit.log" 2>/dev/null || true

if [[ ! -f "${ROOT}/.env" ]]; then
  cp "${ROOT}/.env.example" "${ROOT}/.env"
  if ! grep -q '^USE_LITELLM_PROXY=' "${ROOT}/.env"; then
    echo "USE_LITELLM_PROXY=false" >>"${ROOT}/.env"
  else
    sed -i 's/^USE_LITELLM_PROXY=.*/USE_LITELLM_PROXY=false/' "${ROOT}/.env" 2>/dev/null || true
  fi
  log "已从 .env.example 生成 .env（LoongArch 默认关闭 LiteLLM 代理）"
  log "请编辑 .env 填写 LLM_API_KEY 后执行: bash boot_start.sh"
fi

log "创建虚拟环境 (本机架构)..."
rm -rf "${ROOT}/.venv"
"${UV}" sync

if [[ ! -d "${ROOT}/frontend/dist" ]] && [[ -f "${ROOT}/frontend/package.json" ]]; then
  if command -v npm >/dev/null 2>&1; then
    log "未找到 frontend/dist，正在本机构建前端..."
    (cd "${ROOT}/frontend" && npm install && npm run build) || log "前端构建失败，可稍后在 x86 机打包 dist 再拷入"
  else
    log "无 frontend/dist 且无 npm，请使用含 dist 的发布包或在 x86 机构建后拷贝"
  fi
fi

log "完成。下一步:"
log "  1. 编辑 .env（LLM_API_KEY、SEC_API_HOST=0.0.0.0）"
log "  2. bash boot_start.sh"
log "  3. 浏览器 http://$(hostname -I 2>/dev/null | awk '{print $1}'):8900/"
log "详细说明: docs/DEPLOY_KYLIN_LOONGARCH.md"

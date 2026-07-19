#!/bin/bash
# 麒麟 V11 LoongArch 首次初始化
# 自动检测 uv 是否可用，不可用则降级到 pip
# 用法: bash scripts/bootstrap-kylin-loongarch.sh
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

log() { echo "[bootstrap] $*"; }

ARCH="$(uname -m)"
log "架构: ${ARCH} · $(grep -E '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2- | tr -d '\"' || uname -s)"
log "仅支持 LoongArch 麒麟部署，其他可用平台请参考 docs/"

# ---- 1. 系统依赖 ----
log "安装系统依赖..."
sudo dnf install -y python3 python3-pip python3-devel gcc gcc-c++ make curl libffi-devel openssl-devel 2>/dev/null || true

# ---- 2. Python 虚拟环境 ----
USE_UV=false

if command -v uv >/dev/null 2>&1; then
  USE_UV=true
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  export PATH="${HOME}/.local/bin:${PATH}"
  USE_UV=true
else
  log "uv 未安装，尝试在线安装..."
  if curl -fsSL --connect-timeout 10 https://astral.sh/uv/install.sh -o /tmp/uv-install.sh 2>/dev/null; then
    sh /tmp/uv-install.sh 2>/dev/null && export PATH="${HOME}/.local/bin:${PATH}" && USE_UV=true && log "uv 安装成功" || log "uv 安装失败（loongarch64 无预编译包）"
  else
    log "无法连接 uv 官网"
  fi
fi

if [[ "${USE_UV}" == true ]] && command -v uv >/dev/null 2>&1; then
  log "使用 uv 安装依赖..."
  rm -rf .venv
  uv sync
else
  # ---- 降级：pip + venv ----
  log "uv 不可用，降级到 pip + venv..."
  rm -rf .venv
  python3 -m venv .venv
  source .venv/bin/activate

  log "升级 pip..."
  pip install --upgrade pip -q

  log "安装核心依赖（纯 Python，无需编译）..."
  pip install httpx openai python-dotenv fastapi uvicorn \
    "python-multipart>=0.0.18" PyJWT "passlib>=1.7.4" \
    websockets pyyaml slowapi tenacity psutil

  log "安装含 C 扩展的依赖（龙架构需编译，稍等）..."
  pip install numpy pandas matplotlib pillow 2>/dev/null || log "⚠️ 部分可选包编译失败，核心功能不受影响"

  log "安装项目自身..."
  pip install -e . --no-deps
fi

# ---- 3. 生成 .env ----
if [[ ! -f .env ]]; then
  cp .env.example .env
  sed -i 's/^USE_LITELLM_PROXY=.*/USE_LITELLM_PROXY=false/' .env 2>/dev/null || true
  log "已生成 .env，请编辑 LLM_API_KEY"
else
  log ".env 已存在，跳过"
fi

# ---- 4. 目录 ----
mkdir -p data/logs data/reports
touch data/audit.log 2>/dev/null || true

# ---- 5. 前端 ----
if [[ ! -f frontend/dist/index.html ]]; then
  log "⚠️ 缺少 frontend/dist/ — 请从 x86 机拷贝或 npm run build"
fi

# ---- 完成 ----
log "========================================="
log "  初始化完成"
log "  "
log "  1. vi .env    (填 LLM_API_KEY)"
log "  2. bash boot_start.sh"
log "  3. 浏览器 http://$(hostname -I 2>/dev/null | awk '{print $1}'):8900/"
log "========================================="

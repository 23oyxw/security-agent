#!/usr/bin/env bash
# LoongArch/Kylin 一键安装依赖（不用 uv，不用 pip install -e .）
set -euo pipefail

SEC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${SEC_ROOT}"

log() { echo "[bootstrap-loongarch] $*"; }

if ! command -v python3 >/dev/null 2>&1; then
  log "安装 python3..."
  sudo dnf install -y python3 python3-pip python3-devel gcc gcc-c++ make \
    libffi-devel openssl-devel || true
fi

log "修复 Windows 换行符..."
find . -name '*.sh' -exec sed -i 's/\r$//' {} + 2>/dev/null || true

if [[ ! -d .venv ]]; then
  log "创建虚拟环境..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

PIP_INDEX="${PIP_INDEX:-https://mirrors.aliyun.com/pypi/simple}"
REQ="${SEC_ROOT}/requirements-loongarch.txt"

if [[ ! -f "${REQ}" ]]; then
  log "缺少 ${REQ}" >&2
  exit 1
fi

log "安装系统编译依赖（cryptography/mcp 可能需要）..."
sudo dnf install -y libffi-devel openssl-devel python3-devel gcc gcc-c++ 2>/dev/null || true

log "pip 安装依赖（龙芯请耐心等待）..."
pip install -i "${PIP_INDEX}" -r "${REQ}"

mkdir -p data/logs data/reports
touch data/audit.log 2>/dev/null || true

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  log "已从 .env.example 生成 .env，请编辑 LLM_API_KEY"
fi

log "完成。启动: bash scripts/boot_start_loongarch.sh"

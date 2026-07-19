#!/usr/bin/env bash
# LoongArch/Kylin 一键安装依赖（不用 uv，不用 pip install -e .）
set -eu

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
REQ_MIN="${SEC_ROOT}/requirements-loongarch-min.txt"
REQ_OPT="${SEC_ROOT}/requirements-loongarch-optional.txt"

if [[ ! -f "${REQ_MIN}" ]]; then
  log "缺少 ${REQ_MIN}" >&2
  exit 1
fi

log "安装系统编译依赖（cryptography/mcp 可能需要）..."
sudo dnf install -y libffi-devel openssl-devel python3-devel gcc gcc-c++ 2>/dev/null || true

log "pip 安装最小依赖（B/S 答辩）..."
pip install -i "${PIP_INDEX}" -r "${REQ_MIN}"

if [[ "${LOONGARCH_FULL:-0}" == "1" && -f "${REQ_OPT}" ]]; then
  log "安装可选依赖（pandas/streamlit 等，失败可忽略）..."
  pip install -i "${PIP_INDEX}" -r "${REQ_OPT}" || log "可选依赖部分安装失败，B/S 不受影响"
fi

mkdir -p data/logs data/reports
touch data/audit.log 2>/dev/null || true

if [[ ! -f .env && -f .env.example ]]; then
  cp .env.example .env
  log "已从 .env.example 生成 .env，请编辑 LLM_API_KEY"
fi

log "完成。启动: bash scripts/boot_start_loongarch.sh"

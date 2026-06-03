#!/usr/bin/env bash
# 目录改名后若打不开，先运行本脚本一次
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"
UV="${HOME}/.local/bin/uv"
command -v uv &>/dev/null && UV="$(command -v uv)"
echo "[修复] 停止旧进程…"
bash "${ROOT}/boot_stop.sh" || true
echo "[修复] 重建虚拟环境…"
rm -rf .venv
"${UV}" sync
echo "[修复] 完成。请再双击「打开应用」或运行: bash boot_start.sh"

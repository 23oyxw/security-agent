#!/usr/bin/env bash
# 麒麟桌面双击启动（终端保持打开，便于看日志）
cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
echo "正在启动安全运维 Agent..."
bash ./start.sh "$@" || true
echo ""
read -r -p "按 Enter 键关闭本窗口…" _

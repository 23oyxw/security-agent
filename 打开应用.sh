#!/usr/bin/env bash
#==============================================================================
# 安全运维 Agent — 统一控制台入口（麒麟桌面双击启动）
# 自动启动服务 + 打开 Web 控制面板
#==============================================================================
set -eu

ROOT="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
PORT="${SEC_API_PORT:-8900}"
PANEL="${ROOT}/web-control.html"

export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
cd "${ROOT}"

echo ""
echo "  🛡️  银河麒麟智能安全运维 Agent"
echo "  ================================="

# 启动服务（如未运行）
if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/api/health" 2>/dev/null; then
    echo "  ✅ 服务已运行 → http://127.0.0.1:${PORT}"
else
    echo "  🚀 正在启动服务..."
    bash ./boot_start.sh 2>&1 | grep -E '✅|❌|启动|文档|控制台' || true
fi

echo ""
echo "  📋 快捷入口:"
echo "     控制台:   http://127.0.0.1:${PORT}/"
echo "     API 文档: http://127.0.0.1:${PORT}/docs"
echo "     健康检查: http://127.0.0.1:${PORT}/api/health"
echo ""
echo "  🛑 停止: bash ${ROOT}/stop.sh"
echo "  ================================="
echo ""

# 尝试打开 Web 控制面板到默认浏览器
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${PANEL}" >/dev/null 2>&1 &
elif command -v qaxbrowser >/dev/null 2>&1; then
    qaxbrowser "file://${PANEL}" >/dev/null 2>&1 &
elif command -v firefox >/dev/null 2>&1; then
    firefox "file://${PANEL}" >/dev/null 2>&1 &
fi

read -r -p "按 Enter 键关闭本窗口…" _

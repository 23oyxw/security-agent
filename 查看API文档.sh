#!/bin/bash
#==============================================================================
# 快捷打开 API 文档（Swagger UI + ReDoc）
# 自动检测 API 是否运行，未运行则启动
#==============================================================================
set -eu

ROOT="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
PORT="${SEC_API_PORT:-8900}"
export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

echo ""
echo "  📄 安全运维 Agent — API 文档"
echo "  ================================="

if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/api/health" 2>/dev/null; then
    echo "  ✅ API 服务运行中"
else
    echo "  🚀 API 未运行，正在启动..."
    cd "${ROOT}" && bash boot_start.sh 2>&1 | grep -E '✅|❌|启动|FastAPI' || true
    sleep 2
fi

echo ""
echo "  📋 文档入口:"
echo "     Swagger UI: http://127.0.0.1:${PORT}/docs"
echo "     ReDoc:      http://127.0.0.1:${PORT}/redoc"
echo "     健康检查:   http://127.0.0.1:${PORT}/api/health"
echo ""
echo "  🛑 停止: bash ${ROOT}/stop.sh"
echo "  ================================="
echo ""

# 打开 Swagger UI
DOCS_URL="http://127.0.0.1:${PORT}/docs"
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${DOCS_URL}" 2>/dev/null &
elif command -v qaxbrowser >/dev/null 2>&1; then
    qaxbrowser "${DOCS_URL}" 2>/dev/null &
elif command -v firefox >/dev/null 2>&1; then
    firefox "${DOCS_URL}" 2>/dev/null &
fi

read -r -p "按 Enter 键关闭本窗口…" _
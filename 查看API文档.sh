#!/usr/bin/env bash
# 快捷打开 API 文档（Swagger UI）
cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"

PORT="${SEC_API_PORT:-8900}"
DOCS_URL="http://127.0.0.1:${PORT}/docs"

# 检查 API 是否正在运行
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/api/health" 2>/dev/null | grep -q "200"; then
    echo "✅ API 服务运行中，正在打开文档..."
else
    echo "⚠️  API 服务未运行，正在启动..."
    bash ./start.sh &
    sleep 3
fi

echo "📄 API 文档地址: ${DOCS_URL}"
echo "   Swagger UI  : ${DOCS_URL}"
echo "   ReDoc       : http://127.0.0.1:${PORT}/redoc"
echo ""

# 尝试打开浏览器
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${DOCS_URL}" 2>/dev/null &
elif command -v qaxbrowser >/dev/null 2>&1; then
    qaxbrowser "${DOCS_URL}" 2>/dev/null &
elif command -v firefox >/dev/null 2>&1; then
    firefox "${DOCS_URL}" 2>/dev/null &
fi

echo "按 Enter 键关闭本窗口…"
read -r _
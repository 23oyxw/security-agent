#!/usr/bin/env bash
# P0 API 段自动化（浏览器段见 docs/P0_FRONTEND_WALKTHROUGH.md）
set -eu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SEC_API_HOST:-127.0.0.1}"
PORT="${SEC_API_PORT:-8900}"
BASE="http://${HOST}:${PORT}"

pass=0
fail=0

check() {
  local name="$1" code="$2" expect="$3"
  if [[ "$code" == "$expect" ]]; then
    echo "  [PASS] $name ($code)"
    pass=$((pass + 1))
  else
    echo "  [FAIL] $name (got $code, want $expect)"
    fail=$((fail + 1))
  fi
}

echo "=== P0 API 联调检查 → $BASE ==="
echo "（若失败请先: bash boot_start.sh）"
echo ""

if ! curl -sf --max-time 3 "${BASE}/api/health" >/dev/null 2>&1; then
  echo "  [SKIP] API 未启动，跳过 curl 段。请启动后重试。"
  echo ""
  echo "  浏览器清单: docs/P0_FRONTEND_WALKTHROUGH.md"
  exit 0
fi

code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/api/health")
check "GET /api/health" "$code" "200"

code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/api/health/ready")
check "GET /api/health/ready" "$code" "200"

login=$(curl -s -X POST "${BASE}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}')
token=$(echo "$login" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
if [[ -z "$token" ]]; then
  echo "  [FAIL] POST /api/auth/login (no token)"
  fail=$((fail + 1))
else
  echo "  [PASS] POST /api/auth/login"
  pass=$((pass + 1))
  AUTH=(-H "Authorization: Bearer ${token}")

  for path in \
    "/api/perception/metrics" \
    "/api/alerts/" \
    "/api/mcp/servers" \
    "/api/trace/" \
    "/api/safety/pending"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}${path}" "${AUTH[@]}")
    check "GET ${path}" "$code" "200"
  done

  deny=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE}/api/safety/defense/evaluate" \
    "${AUTH[@]}" -H 'Content-Type: application/json' \
    -d '{"target":"rm -rf /","target_type":"terminal","user_message":"删除"}')
  check "POST /api/safety/defense/evaluate (deny path)" "$deny" "200"

  root_code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/")
  check "GET / (SPA)" "$root_code" "200"
fi

echo ""
echo "=== P0 API 段: ${pass} 通过, ${fail} 失败 ==="
echo "下一步: 按 docs/P0_FRONTEND_WALKTHROUGH.md 完成浏览器 10 页签字"
[[ "$fail" -eq 0 ]]

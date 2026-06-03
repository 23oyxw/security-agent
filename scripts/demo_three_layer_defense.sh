#!/usr/bin/env bash
# 三层防御 + 最小权限 + Trace 答辩演示（约 3 分钟）
# 用法: bash scripts/demo_three_layer_defense.sh [API_BASE]
# 默认 API_BASE=http://127.0.0.1:8900（与 boot_start.sh 一致）

set -euo pipefail

API_BASE="${1:-http://127.0.0.1:8900}"
SEC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { echo ""; echo ">>> $*"; }

log "1/5 健康检查"
curl -sf "${API_BASE}/api/health" | python3 -m json.tool 2>/dev/null || curl -sf "${API_BASE}/api/health"

log "2/5 登录获取 Token"
TOKEN=$(curl -sf -X POST "${API_BASE}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
if [[ -z "${TOKEN}" ]]; then
  echo "登录失败，请确认 API 已启动: bash boot_start.sh" >&2
  exit 1
fi
AUTH="Authorization: Bearer ${TOKEN}"

log "3/5 三层防御 — 允许 (ls -la)"
curl -sf -X POST "${API_BASE}/api/safety/defense/evaluate" \
  -H "Content-Type: application/json" -H "${AUTH}" \
  -d '{"target":"ls -la /tmp","target_type":"terminal","user_message":"查看临时目录"}' \
  | python3 -m json.tool 2>/dev/null | head -30

log "4/5 三层防御 — 拒绝 (rm -rf)"
curl -sf -X POST "${API_BASE}/api/safety/defense/evaluate" \
  -H "Content-Type: application/json" -H "${AUTH}" \
  -d '{"target":"rm -rf /","target_type":"terminal","user_message":"清理临时文件"}' \
  | python3 -m json.tool 2>/dev/null | head -30

log "5/5 L2 扫描报告 Flow + Trace 列表"
curl -sf -X POST "${API_BASE}/api/skills/flows/scan_report/run" \
  -H "Content-Type: application/json" -H "${AUTH}" \
  -d '{"context":{}}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('flow=',d.get('flow'),'ok=',d.get('ok'),'trace_id=',d.get('trace_id'))"

curl -sf "${API_BASE}/api/trace/?limit=3" -H "${AUTH}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('traces=',len(d.get('traces',[])))"

log "演示完成。浏览器打开: ${API_BASE}/  → 登录 admin/admin123 → 安全门禁 / 运维流程"

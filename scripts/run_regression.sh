#!/usr/bin/env bash
# 发版前回归：核心单测 + API E2E（无需 pytest）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
export PYTHONPATH="$ROOT"

if [[ ! -x "$PY" ]]; then
  echo "缺少 .venv，请先: uv sync"
  exit 1
fi

TESTS=(
  tests/test_three_layer_defense.py
  tests/test_react_context.py
  tests/test_incident_spine.py
  tests/test_enterprise_ops.py
  tests/test_dify_bridge.py
  tests/test_skill_flows.py
)

echo "=== 回归单测 ==="
for t in "${TESTS[@]}"; do
  echo ">> $t"
  "$PY" "$t" || exit 1
done

echo ""
echo "=== API E2E 冒烟 ==="
"$PY" scripts/e2e_api_smoke.py
echo ""
echo "=== 回归全部通过 ==="

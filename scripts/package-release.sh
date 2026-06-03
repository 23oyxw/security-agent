#!/usr/bin/env bash
# 打包项目发给小组
#   bash scripts/package-release.sh          # 精简包（无 .venv / .env）
#   bash scripts/package-release.sh --full   # 完整内网包（含 .venv、.env，组长配置原样带走）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

FULL=0
[[ "${1:-}" == "--full" || "${1:-}" == "-f" ]] && FULL=1

VERSION="$(grep -E '^version\s*=' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')"
STAMP="$(date '+%Y%m%d')"
SUFFIX=""
[[ "${FULL}" -eq 1 ]] && SUFFIX="-full"
NAME="security-agent-v${VERSION}-${STAMP}${SUFFIX}"
OUT_DIR="${ROOT}/dist"
ARCHIVE="${OUT_DIR}/${NAME}.tar.gz"

mkdir -p "${OUT_DIR}" "${ROOT}/data/logs" "${ROOT}/data/reports"

EXCLUDES=(
  --exclude='dist'
  --exclude='__pycache__'
  --exclude='*.py[oc]'
  --exclude='.cursor'
  --exclude='data/.streamlit.pid'
  --exclude='data/.api.pid'
  --exclude='data/.litellm.pid'
  --exclude='*.egg-info'
  --exclude='.git'
  # 参考库 / 前端依赖（目标机重装）
  --exclude='qt01'
  --exclude='aiflowy-main'
  --exclude='frontend/node_modules'
  # LiteLLM Postgres 数据（Docker nobody 0700，勿打包；目标机 compose 会新建）
  --exclude='data/litellm/pgdata'
  --exclude='data/litellm/pgdata2'
)

if [[ "${FULL}" -eq 0 ]]; then
  EXCLUDES+=(
    --exclude='.venv'
    --exclude='.env'
    --exclude='data/logs'
    --exclude='data/reports'
    --exclude='data/audit.log'
    --exclude='data/traces.db'
    --exclude='data/conversations.db'
    --exclude='data/alerts'
    --exclude='data/*.db'
  )
else
  EXCLUDES+=(
    --exclude='data/logs/*.log'
    --exclude='data/litellm/pgdata'
    --exclude='data/litellm/pgdata2'
  )
  echo "[package] 完整内网包：包含 .venv、.env（不含 LiteLLM pgdata）"
fi

tar -czf "${ARCHIVE}" \
  --transform "s,^,${NAME}/," \
  "${EXCLUDES[@]}" \
  -C "${ROOT}" \
  .

if [[ "${FULL}" -eq 0 ]] && tar -tzf "${ARCHIVE}" | grep -qE '/\.env$'; then
  echo "错误: 精简包内不应含有 .env" >&2
  rm -f "${ARCHIVE}"
  exit 1
fi

if [[ "${FULL}" -eq 1 ]]; then
  for must in '.env' '.venv/pyvenv.cfg' '发给小组-打包说明.md'; do
    tar -tzf "${ARCHIVE}" | grep -qF "${NAME}/${must}" || \
    tar -tzf "${ARCHIVE}" | grep -qF "${NAME}/./${must}" || {
      echo "警告: 完整包缺少 ${must}" >&2
    }
  done
fi

BYTES="$(wc -c <"${ARCHIVE}")"
HUMAN="$(numfmt --to=iec-i --suffix=B "${BYTES}" 2>/dev/null || echo "${BYTES} bytes")"
echo ""
echo "已生成: ${ARCHIVE}"
echo "大小:   ${HUMAN}"
echo "解压:   tar -xzf $(basename "${ARCHIVE}") && cd ${NAME}"
if [[ "${FULL}" -eq 1 ]]; then
  echo "请先读: ${NAME}/发给小组-打包说明.md"
else
  echo "请先读: ${NAME}/发给小组-使用说明.txt"
fi

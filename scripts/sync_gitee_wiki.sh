#!/bin/bash
# ============================================================================
# Gitee Wiki 知识库 — 定时同步脚本
#
# 用法:
#   bash scripts/sync_gitee_wiki.sh
#
# 环境变量:
#   GITEE_API_TOKEN       Gitee 个人访问令牌 (必需)
#   GITEE_WIKI_OWNER      Gitee 仓库所有者
#   GITEE_WIKI_REPO       Gitee 仓库名
#
# Cron 示例 (每天凌晨 2 点):
#   0 2 * * * cd /path/to/security-agent && bash scripts/sync_gitee_wiki.sh >> data/logs/wiki_sync.log 2>&1
# ============================================================================

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ---- 检查环境变量 ----
if [ -z "${GITEE_API_TOKEN:-}" ]; then
    echo "[ERROR] GITEE_API_TOKEN 未设置"
    exit 1
fi

if [ -z "${GITEE_WIKI_OWNER:-}" ]; then
    echo "[ERROR] GITEE_WIKI_OWNER 未设置（Gitee 仓库所有者）"
    exit 1
fi

if [ -z "${GITEE_WIKI_REPO:-}" ]; then
    echo "[ERROR] GITEE_WIKI_REPO 未设置（Gitee 仓库名）"
    exit 1
fi

# ---- 日志 ----
LOG_DIR="$PROJECT_ROOT/data/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/wiki_sync_$(date +%Y%m%d).log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步 Wiki: $GITEE_WIKI_OWNER/$GITEE_WIKI_REPO" | tee -a "$LOG_FILE"

# ---- 执行同步 ----
PYTHON="${PROJECT_ROOT}/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    PYTHON=python3
fi

if $PYTHON -m security_agent.knowledge.gitee_wiki.sync \
    --repo-owner "$GITEE_WIKI_OWNER" \
    --repo-name "$GITEE_WIKI_REPO" \
    2>&1 | tee -a "$LOG_FILE"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 同步成功" | tee -a "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 同步失败" | tee -a "$LOG_FILE"
    exit 1
fi

# ---- 清理 7 天前的日志 ----
find "$LOG_DIR" -name "wiki_sync_*.log" -mtime +7 -delete 2>/dev/null || true

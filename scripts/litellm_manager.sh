#!/usr/bin/env bash
#===============================================================================
# LiteLLM 代理管理脚本 — 一键启动/停止/查看状态
#
# 用法:
#   bash scripts/litellm_manager.sh start    # 启动 LiteLLM 代理
#   bash scripts/litellm_manager.sh stop     # 停止 LiteLLM 代理
#   bash scripts/litellm_manager.sh status   # 查看状态
#   bash scripts/litellm_manager.sh restart  # 重启
#   bash scripts/litellm_manager.sh enable   # 启用 LiteLLM（修改 .env）
#   bash scripts/litellm_manager.sh disable  # 禁用 LiteLLM（修改 .env）
#===============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${ROOT}/configs/litellm_config.yaml"
ENV_FILE="${ROOT}/.env"
PID_FILE="${ROOT}/data/.litellm.pid"
LOG_FILE="${ROOT}/data/logs/litellm.log"
PORT=4000

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[LiteLLM]${NC} $1"; }
success() { echo -e "${GREEN}[LiteLLM]${NC} $1"; }
warn()  { echo -e "${YELLOW}[LiteLLM]${NC} $1"; }
error() { echo -e "${RED}[LiteLLM]${NC} $1"; }

# 检查是否可用 litellm（通过 uv run，避免 KYSEC 下全局安装失败）
check_litellm() {
    if ! command -v uv &>/dev/null; then
        error "未找到 uv，请先安装: https://docs.astral.sh/uv/"
        return 1
    fi
    cd "$ROOT"
    if ! uv run litellm --version &>/dev/null; then
        info "尝试安装 litellm（核心包，不含 proxy 可选依赖）..."
        uv pip install 'litellm>=1.63.0' 2>/dev/null || true
        if ! uv run litellm --version &>/dev/null; then
            error "LiteLLM 不可用。银河麒麟环境请优先: bash scripts/litellm_docker.sh start"
            return 1
        fi
    fi
    return 0
}

# 检查配置文件
check_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "配置文件不存在: $CONFIG_FILE"
        return 1
    fi

    # 检查是否配置了 API Key
    if grep -q "your_key_here\|sk-placeholder\|replace-with-real" "$CONFIG_FILE" 2>/dev/null; then
        warn "配置文件中含有占位符 API Key"
        info "请编辑 $CONFIG_FILE，填入真实的 API Key"
        return 1
    fi

    return 0
}

# 获取 PID
get_pid() {
    if [[ -f "$PID_FILE" ]]; then
        cat "$PID_FILE" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

# 检查是否运行中
is_running() {
    local pid=$(get_pid)
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

# 启动 LiteLLM
cmd_start() {
    if is_running; then
        success "LiteLLM 已在运行 (PID: $(get_pid))"
        info "访问: http://localhost:$PORT"
        return 0
    fi

    if ! check_litellm; then
        return 1
    fi

    if ! check_config; then
        return 1
    fi

    info "正在启动 LiteLLM 代理..."
    info "配置: $CONFIG_FILE"
    info "端口: $PORT"
    info "日志: $LOG_FILE"

    mkdir -p "$(dirname "$LOG_FILE")"

    cd "$ROOT"
    nohup uv run litellm --config "$CONFIG_FILE" --port "$PORT" >>"$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"

    # 等待启动
    sleep 2

    if kill -0 "$pid" 2>/dev/null; then
        success "LiteLLM 已启动 (PID: $pid)"
        success "代理地址: http://localhost:$PORT/v1"
        info "查看日志: tail -f $LOG_FILE"

        # 检查是否在 .env 中启用
        if [[ -f "$ENV_FILE" ]] && grep -q "USE_LITELLM_PROXY=true" "$ENV_FILE"; then
            success "✓ 已配置为使用 LiteLLM 代理"
        else
            warn "⚠ 当前 .env 中未启用 LiteLLM (USE_LITELLM_PROXY=false)"
            info "运行 'bash scripts/litellm_manager.sh enable' 启用"
        fi
    else
        error "启动失败，请查看日志: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# 停止 LiteLLM
cmd_stop() {
    local pid=$(get_pid)

    if ! is_running; then
        info "LiteLLM 未运行"
        rm -f "$PID_FILE"
        return 0
    fi

    info "正在停止 LiteLLM (PID: $pid)..."
    kill "$pid" 2>/dev/null || true
    sleep 1

    # 强制终止
    if kill -0 "$pid" 2>/dev/null; then
        warn "进程未响应，强制终止..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    success "LiteLLM 已停止"
}

# 查看状态
cmd_status() {
    if is_running; then
        local pid=$(get_pid)
        success "LiteLLM 正在运行 (PID: $pid)"
        info "代理地址: http://localhost:$PORT/v1"
        info "日志文件: $LOG_FILE"

        # 检查是否已启用
        if [[ -f "$ENV_FILE" ]] && grep -q "USE_LITELLM_PROXY=true" "$ENV_FILE"; then
            success "✓ 已在 .env 中启用"
        else
            warn "⚠ 未在 .env 中启用"
        fi

        # 显示最后几行日志
        if [[ -f "$LOG_FILE" ]]; then
            info "最近日志:"
            tail -n 3 "$LOG_FILE" | sed 's/^/  /'
        fi
    else
        warn "LiteLLM 未运行"
        rm -f "$PID_FILE"
    fi
}

# 重启
cmd_restart() {
    cmd_stop || true
    sleep 1
    cmd_start
}

# 启用 LiteLLM（修改 .env）
cmd_enable() {
    if [[ ! -f "$ENV_FILE" ]]; then
        error ".env 文件不存在"
        return 1
    fi

    info "正在启用 LiteLLM..."

    # 修改 .env
    sed -i 's/^USE_LITELLM_PROXY=.*/USE_LITELLM_PROXY=true/' "$ENV_FILE" 2>/dev/null || \
        sed -i '' 's/^USE_LITELLM_PROXY=.*/USE_LITELLM_PROXY=true/' "$ENV_FILE" 2>/dev/null || true

    # 如果没有这行，添加
    if ! grep -q "^USE_LITELLM_PROXY" "$ENV_FILE"; then
        echo "USE_LITELLM_PROXY=true" >> "$ENV_FILE"
    fi

    success "✓ 已启用 LiteLLM 代理模式"
    info "重启应用后生效: bash boot_stop.sh && bash boot_start.sh"

    # 检查 LiteLLM 是否运行
    if ! is_running; then
        warn "LiteLLM 代理尚未启动"
        info "运行: bash scripts/litellm_manager.sh start"
    fi
}

# 禁用 LiteLLM
cmd_disable() {
    if [[ ! -f "$ENV_FILE" ]]; then
        error ".env 文件不存在"
        return 1
    fi

    info "正在禁用 LiteLLM..."

    sed -i 's/^USE_LITELLM_PROXY=.*/USE_LITELLM_PROXY=false/' "$ENV_FILE" 2>/dev/null || \
        sed -i '' 's/^USE_LITELLM_PROXY=.*/USE_LITELLM_PROXY=false/' "$ENV_FILE" 2>/dev/null || true

    success "✓ 已禁用 LiteLLM 代理模式"
    info "应用将直接连接模型 API"
    info "重启应用后生效: bash boot_stop.sh && bash boot_start.sh"
}

# 显示帮助
cmd_help() {
    cat <<EOF
LiteLLM 代理管理工具

用法: bash scripts/litellm_manager.sh <命令>

命令:
  start      启动 LiteLLM 代理
  stop       停止 LiteLLM 代理
  status     查看运行状态
  restart    重启 LiteLLM 代理
  enable     启用 LiteLLM 模式（修改 .env）
  disable    禁用 LiteLLM 模式（修改 .env）
  help       显示帮助

快速开始:
  1. 安装: pip install 'litellm[proxy]'
  2. 启动: bash scripts/litellm_manager.sh start
  3. 启用: bash scripts/litellm_manager.sh enable
  4. 重启应用: bash boot_stop.sh && bash boot_start.sh

EOF
}

# 主入口
case "${1:-help}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    status)
        cmd_status
        ;;
    restart)
        cmd_restart
        ;;
    enable)
        cmd_enable
        ;;
    disable)
        cmd_disable
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        error "未知命令: $1"
        cmd_help
        exit 1
        ;;
esac

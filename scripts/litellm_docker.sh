#!/usr/bin/env bash
#===============================================================================
# LiteLLM Docker 管理脚本 — 企业级部署方案
#
# 优势：
#   - 无需本地安装 Python 依赖
#   - 容器化隔离，环境稳定
#   - 企业级常用部署方式
#   - 一键启动/停止/查看日志
#
# 用法：
#   bash scripts/litellm_docker.sh start    # 启动
#   bash scripts/litellm_docker.sh stop     # 停止
#   bash scripts/litellm_docker.sh status   # 查看状态
#   bash scripts/litellm_docker.sh logs     # 查看日志
#===============================================================================

set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT}/configs/docker-compose.litellm.yml"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[LiteLLM-Docker]${NC} $1"; }
success() { echo -e "${GREEN}[LiteLLM-Docker]${NC} $1"; }
warn()  { echo -e "${YELLOW}[LiteLLM-Docker]${NC} $1"; }
error() { echo -e "${RED}[LiteLLM-Docker]${NC} $1"; }

# 检查 Docker
check_docker() {
    if ! command -v docker &>/dev/null; then
        error "未找到 Docker 命令"
        info "请安装 Docker: https://docs.docker.com/get-docker/"
        return 1
    fi

    if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
        error "未找到 Docker Compose"
        info "Docker Desktop 自带，或单独安装"
        return 1
    fi

    # 检查 Docker 是否运行
    if ! docker info &>/dev/null; then
        error "Docker 守护进程未运行"
        info "请启动 Docker 服务"
        return 1
    fi

    return 0
}

# 获取 compose 命令（兼容新旧版本）
get_compose_cmd() {
    if docker compose version &>/dev/null; then
        echo "docker compose"
    else
        echo "docker-compose"
    fi
}

# 启动 LiteLLM
cmd_start() {
    if ! check_docker; then
        return 1
    fi

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        error "Compose 文件不存在: $COMPOSE_FILE"
        return 1
    fi

    COMPOSE_CMD=$(get_compose_cmd)

    info "正在启动 LiteLLM 容器..."
    cd "$ROOT"
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d

    # 等待健康检查
    info "等待服务就绪..."
    sleep 3

    # 检查是否启动成功
    if docker ps | grep -q "security-agent-litellm"; then
        success "✅ LiteLLM 容器已启动"
        info "代理地址: http://localhost:4000/v1"
        info "查看日志: bash scripts/litellm_docker.sh logs"

        # 检查 .env 配置
        if [[ -f "${ROOT}/.env" ]] && grep -q "USE_LITELLM_PROXY=true" "${ROOT}/.env"; then
            success "✓ 已配置使用 LiteLLM 代理"
        else
            warn "⚠ .env 中未启用 LiteLLM 代理"
            info "运行: bash scripts/litellm_manager.sh enable"
        fi
    else
        error "容器启动失败"
        info "查看日志: $COMPOSE_CMD -f $COMPOSE_FILE logs"
        return 1
    fi
}

# 停止 LiteLLM
cmd_stop() {
    COMPOSE_CMD=$(get_compose_cmd)

    info "正在停止 LiteLLM 容器..."
    cd "$ROOT"
    $COMPOSE_CMD -f "$COMPOSE_FILE" down
    success "✅ LiteLLM 容器已停止"
}

# 重启
cmd_restart() {
    cmd_stop || true
    sleep 2
    cmd_start
}

# 查看状态
cmd_status() {
    if ! docker ps | grep -q "security-agent-litellm"; then
        warn "LiteLLM 容器未运行"
        return 0
    fi

    success "✅ LiteLLM 容器运行中"
    info "容器信息:"
    docker ps --filter "name=security-agent-litellm" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    # 健康检查
    info "健康检查..."
    if curl -s http://localhost:4000/health/liveliness &>/dev/null; then
        success "✓ 服务健康"
    else
        warn "⚠ 健康检查未通过，可能正在启动中"
    fi
}

# 查看日志
cmd_logs() {
    COMPOSE_CMD=$(get_compose_cmd)
    cd "$ROOT"
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f
}

# 更新镜像
cmd_update() {
    COMPOSE_CMD=$(get_compose_cmd)
    info "拉取最新镜像..."
    cd "$ROOT"
    docker pull ghcr.io/berriai/litellm:main-latest
    success "✅ 镜像已更新，请重启服务"
}

# 帮助
cmd_help() {
    cat <<EOF
LiteLLM Docker 管理工具 — 企业级容器化部署

用法: bash scripts/litellm_docker.sh <命令>

命令:
  start      启动 LiteLLM 容器
  stop       停止 LiteLLM 容器
  restart    重启 LiteLLM 容器
  status     查看运行状态
  logs       查看实时日志
  update     更新到最新镜像
  help       显示帮助

快速开始:
  1. 确保已安装 Docker
  2. 配置 litellm_config.yaml
  3. bash scripts/litellm_docker.sh start
  4. bash scripts/litellm_manager.sh enable
  5. bash boot_stop.sh && bash boot_start.sh

优势:
  - 无需处理 Python 依赖问题
  - 容器化隔离，环境稳定
  - 企业级常用部署方式
  - 内置健康检查和自动重启

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
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    update)
        cmd_update
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

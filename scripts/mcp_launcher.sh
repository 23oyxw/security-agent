#!/bin/bash
#==============================================================================
# MCP 服务统一管理脚本
# 用法: bash scripts/mcp_launcher.sh [start|stop|status|restart] [service|all]
#
# 示例:
#   bash scripts/mcp_launcher.sh start all          # 启动所有服务
#   bash scripts/mcp_launcher.sh start healthcheck # 启动单个服务
#   bash scripts/mcp_launcher.sh status            # 查看所有状态
#   bash scripts/mcp_launcher.sh stop all          # 停止所有服务
#==============================================================================

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_DIR="${PROJECT_ROOT}/data/pids"
LOG_DIR="${PROJECT_ROOT}/data/logs"

# 服务配置: 名称 端口 描述
SERVICES=(
    "healthcheck:8081:健康巡检"
    "log_analyzer:8082:日志分析"
    "config_manager:8083:配置管理"
    "security_hardening:8084:安全加固"
    "incident_responder:8085:故障响应"
)

mkdir -p "${PID_DIR}" "${LOG_DIR}"

log() { echo "[MCP] $*"; }

# 检查服务是否运行
check_service() {
    local port=$1
    if curl -sf "http://127.0.0.1:${port}/info" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# 获取服务 PID
get_service_pid() {
    local name=$1
    local pid_file="${PID_DIR}/mcp_${name}.pid"
    if [[ -f "${pid_file}" ]]; then
        cat "${pid_file}" 2>/dev/null || true
    fi
}

# 启动单个服务
start_service() {
    local name=$1
    local port=$2
    local desc=$3
    local pid_file="${PID_DIR}/mcp_${name}.pid"
    local log_file="${LOG_DIR}/mcp_${name}.log"
    
    if check_service "${port}"; then
        log "${desc}(${name}) 已在运行 @ 端口${port}"
        return 0
    fi
    
    log "启动 ${desc}(${name}) @ 端口${port}..."
    
    nohup python3 -m "security_agent.skills.${name}.mcp_server" \
        --transport http \
        --port "${port}" \
        >> "${log_file}" 2>&1 &
    
    local pid=$!
    echo ${pid} > "${pid_file}"
    
    # 等待启动
    local retries=0
    while [[ ${retries} -lt 10 ]]; do
        if check_service "${port}"; then
            log "✅ ${desc}(${name}) 启动成功 (PID ${pid})"
            return 0
        fi
        sleep 1
        ((retries++)) || true
    done
    
    log "❌ ${desc}(${name}) 启动超时，查看日志: ${log_file}"
    return 1
}

# 停止单个服务
stop_service() {
    local name=$1
    local port=$2
    local desc=$3
    local pid_file="${PID_DIR}/mcp_${name}.pid"
    
    local pid=$(get_service_pid "${name}")
    
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
        kill -TERM "${pid}" 2>/dev/null || true
        sleep 1
        if kill -0 "${pid}" 2>/dev/null; then
            kill -KILL "${pid}" 2>/dev/null || true
        fi
        log "已停止 ${desc}(${name}) (PID ${pid})"
    else
        # 尝试通过端口查找
        if command -v lsof &>/dev/null; then
            pid=$(lsof -t -i":${port}" 2>/dev/null || true)
            if [[ -n "${pid}" ]]; then
                kill -TERM ${pid} 2>/dev/null || true
                log "已停止 ${desc}(${name}) (通过端口查找)"
            fi
        fi
    fi
    
    rm -f "${pid_file}"
}

# 查看服务状态
status_service() {
    local name=$1
    local port=$2
    local desc=$3
    
    if check_service "${port}"; then
        local pid=$(get_service_pid "${name}")
        printf "  🟢 %-20s 端口:%-5s PID:%-6s %s\n" "${name}" "${port}" "${pid:-未知}" "${desc}"
    else
        printf "  ⚫ %-20s 端口:%-5s 已停止 %s\n" "${name}" "${port}" "${desc}"
    fi
}

# 启动所有服务
cmd_start() {
    local target=${1:-all}
    
    if [[ "${target}" == "all" ]]; then
        log "正在启动所有 MCP 服务..."
        for svc in "${SERVICES[@]}"; do
            IFS=':' read -r name port desc <<< "${svc}"
            start_service "${name}" "${port}" "${desc}"
        done
        log ""
        log "服务状态:"
        cmd_status
    else
        for svc in "${SERVICES[@]}"; do
            IFS=':' read -r name port desc <<< "${svc}"
            if [[ "${name}" == "${target}" ]]; then
                start_service "${name}" "${port}" "${desc}"
                return 0
            fi
        done
        log "❌ 未知服务: ${target}"
        log "可用服务: healthcheck, log_analyzer, config_manager, security_hardening, incident_responder"
        return 1
    fi
}

# 停止所有服务
cmd_stop() {
    local target=${1:-all}
    
    if [[ "${target}" == "all" ]]; then
        log "正在停止所有 MCP 服务..."
        for svc in "${SERVICES[@]}"; do
            IFS=':' read -r name port desc <<< "${svc}"
            stop_service "${name}" "${port}" "${desc}"
        done
    else
        for svc in "${SERVICES[@]}"; do
            IFS=':' read -r name port desc <<< "${svc}"
            if [[ "${name}" == "${target}" ]]; then
                stop_service "${name}" "${port}" "${desc}"
                return 0
            fi
        done
        log "❌ 未知服务: ${target}"
        return 1
    fi
}

# 查看状态
cmd_status() {
    log "MCP 服务状态:"
    log "----------------------------------------"
    for svc in "${SERVICES[@]}"; do
        IFS=':' read -r name port desc <<< "${svc}"
        status_service "${name}" "${port}" "${desc}"
    done
    log "----------------------------------------"
    
    # 统计
    local running=0
    for svc in "${SERVICES[@]}"; do
        IFS=':' read -r name port desc <<< "${svc}"
        if check_service "${port}"; then
            ((running++)) || true
        fi
    done
    log "运行中: ${running}/${#SERVICES[@]}"
}

# 重启服务
cmd_restart() {
    local target=${1:-all}
    cmd_stop "${target}"
    sleep 2
    cmd_start "${target}"
}

# 查看日志
cmd_logs() {
    local target=${1:-}
    if [[ -z "${target}" || "${target}" == "all" ]]; then
        log "可用日志:"
        for svc in "${SERVICES[@]}"; do
            IFS=':' read -r name port desc <<< "${svc}"
            local log_file="${LOG_DIR}/mcp_${name}.log"
            if [[ -f "${log_file}" ]]; then
                local size=$(stat -c%s "${log_file}" 2>/dev/null || stat -f%z "${log_file}" 2>/dev/null || echo 0)
                printf "  %-20s %6d bytes\n" "${name}" "${size}"
            fi
        done
    else
        local log_file="${LOG_DIR}/mcp_${target}.log"
        if [[ -f "${log_file}" ]]; then
            tail -100 "${log_file}"
        else
            log "日志文件不存在: ${log_file}"
        fi
    fi
}

# 显示帮助
cmd_help() {
    cat << 'HELP'
MCP 服务管理脚本

用法:
  bash scripts/mcp_launcher.sh <命令> [服务名|all]

命令:
  start [service]     启动服务 (默认: all)
  stop [service]      停止服务 (默认: all)
  restart [service]   重启服务 (默认: all)
  status              查看所有服务状态
  logs [service]      查看日志 (默认: 列表)
  help                显示帮助

服务:
  healthcheck         健康巡检 (端口: 8081)
  log_analyzer        日志分析 (端口: 8082)
  config_manager      配置管理 (端口: 8083)
  security_hardening  安全加固 (端口: 8084)
  incident_responder  故障响应 (端口: 8085)

示例:
  # 启动所有服务
  bash scripts/mcp_launcher.sh start all

  # 查看状态
  bash scripts/mcp_launcher.sh status

  # 查看健康巡检日志
  bash scripts/mcp_launcher.sh logs healthcheck

  # 只重启日志分析服务
  bash scripts/mcp_launcher.sh restart log_analyzer
HELP
}

# 主入口
case "${1:-help}" in
    start)
        cmd_start "${2:-all}"
        ;;
    stop)
        cmd_stop "${2:-all}"
        ;;
    restart)
        cmd_restart "${2:-all}"
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs "${2:-}"
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        log "❌ 未知命令: ${1}"
        cmd_help
        exit 1
        ;;
esac

#!/usr/bin/env bash
#===============================================================================
# CPU 压测工具 — 支持单核/多核模式，自动生成 HTML 报告
#
# 用法：
#   bash scripts/stress_cpu.sh                    # 快速模式（单核，5秒）
#   bash scripts/stress_cpu.sh --multi            # 多核压测（使用所有 CPU）
#   bash scripts/stress_cpu.sh --duration 30      # 自定义时长（秒）
#   bash scripts/stress_cpu.sh --report-only      # 只生成报告，不压测
#
# 依赖：
#   - dd (coreutils，通常已安装)
#   - uv (用于运行 Python 报告生成)
#   - stress (可选，用于更精确的压测)
#===============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# 配置与默认值
# -----------------------------------------------------------------------------
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DURATION=5
MODE="single"      # single / multi / report-only
USE_STRESS=false   # 是否使用 stress 工具
QUIET=false

# CPU 信息
CPU_COUNT=$(nproc 2>/dev/null || echo 1)
CPU_MODEL=$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d':' -f2 | xargs || echo "Unknown")

# -----------------------------------------------------------------------------
# 颜色输出
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }

# -----------------------------------------------------------------------------
# 使用说明
# -----------------------------------------------------------------------------
usage() {
    cat <<EOF
CPU 压测工具 — 支持单核/多核压测，自动生成 HTML 报告

用法：
  $(basename "$0") [选项]

选项：
  -m, --multi          多核压测模式（使用 $CPU_COUNT 个核心）
  -d, --duration N     压测时长（秒），默认 5 秒
  -r, --report-only    只生成报告，不启动压测
  -s, --use-stress     使用 stress 工具（如果可用）
  -q, --quiet          安静模式，减少输出
  -h, --help           显示此帮助

示例：
  $(basename "$0")                  # 快速压测单核 5 秒
  $(basename "$0") -m -d 30       # 多核压测 30 秒
  $(basename "$0") -r              # 仅生成当前状态报告

EOF
}

# -----------------------------------------------------------------------------
# 命令行参数解析
# -----------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--multi)
                MODE="multi"
                shift
                ;;
            -d|--duration)
                DURATION="$2"
                shift 2
                ;;
            -r|--report-only)
                MODE="report-only"
                shift
                ;;
            -s|--use-stress)
                USE_STRESS=true
                shift
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                error "未知选项: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 前置检查
# -----------------------------------------------------------------------------
check_requirements() {
    local failed=false

    # 检查 dd
    if ! command -v dd &>/dev/null; then
        error "未找到 'dd' 命令（coreutils），请先安装"
        failed=true
    fi

    # 检查 bc（用于浮点计算）
    if ! command -v bc &>/dev/null; then
        warn "未找到 'bc' 命令，某些计算可能不准确"
    fi

    # 如果使用 stress 模式，检查 stress
    if [[ "$USE_STRESS" == true ]]; then
        if ! command -v stress &>/dev/null; then
            warn "未找到 'stress' 工具，回退到 dd 模式"
            USE_STRESS=false
            info "安装 stress: sudo apt-get install stress (Debian/Ubuntu)"
            info "            : sudo yum install stress (RHEL/CentOS)"
        fi
    fi

    # 非 report-only 模式下需要 uv
    if [[ "$MODE" != "report-only" ]]; then
        if ! command -v uv &>/dev/null; then
            error "未找到 'uv' 命令，请先安装"
            info "安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
            failed=true
        fi
    fi

    if [[ "$failed" == true ]]; then
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# 清理残留压测进程
# -----------------------------------------------------------------------------
cleanup_previous() {
    if [[ "$QUIET" == false ]]; then
        info "清理之前的压测进程..."
    fi

    # 清理 dd 进程
    pkill -f "dd if=/dev/zero of=/dev/null" 2>/dev/null || true
    pkill -f "dd if=/dev/zero bs=1M" 2>/dev/null || true

    # 清理 stress 进程
    pkill -f "^stress" 2>/dev/null || true
    pkill -f "stress --cpu" 2>/dev/null || true

    sleep 1
}

# -----------------------------------------------------------------------------
# 启动压测
# -----------------------------------------------------------------------------
start_stress() {
    if [[ "$MODE" == "report-only" ]]; then
        return 0
    fi

    if [[ "$QUIET" == false ]]; then
        echo ""
        info "启动 CPU 压测..."
        info "  模式: $([[ "$MODE" == "multi" ]] && echo "多核 (${CPU_COUNT} 核心)" || echo "单核")"
        info "  时长: ${DURATION} 秒"
        info "  工具: $([[ "$USE_STRESS" == true ]] && echo "stress" || echo "dd")"
        info "  CPU: ${CPU_MODEL:0:50}"
    fi

    if [[ "$USE_STRESS" == true && "$MODE" == "multi" ]]; then
        # 使用 stress 进行多核压测
        local stress_cpus=$CPU_COUNT
        timeout ${DURATION}s stress --cpu $stress_cpus --quiet &
        STRESS_PID=$!
    elif [[ "$USE_STRESS" == true ]]; then
        # 使用 stress 单核
        timeout ${DURATION}s stress --cpu 1 --quiet &
        STRESS_PID=$!
    elif [[ "$MODE" == "multi" ]]; then
        # 使用多个 dd 进程模拟多核
        DD_PIDS=()
        for i in $(seq 1 $CPU_COUNT); do
            dd if=/dev/zero of=/dev/null bs=1M &
            DD_PIDS+=($!)
        done
        if [[ "$QUIET" == false ]]; then
            info "  已启动 ${#DD_PIDS[@]} 个 dd 进程: ${DD_PIDS[*]}"
        fi
    else
        # 单核 dd
        dd if=/dev/zero of=/dev/null bs=1M &
        DD_PID=$!
        if [[ "$QUIET" == false ]]; then
            info "  dd PID: $DD_PID"
        fi
    fi
}

# -----------------------------------------------------------------------------
# 等待压测升温
# -----------------------------------------------------------------------------
wait_for_heat() {
    if [[ "$MODE" == "report-only" ]]; then
        return 0
    fi

    local wait_time=5
    if [[ "$DURATION" -lt 10 ]]; then
        wait_time=3
    fi

    if [[ "$QUIET" == false ]]; then
        info "等待 ${wait_time} 秒让 CPU 升温..."
    fi
    sleep $wait_time
}

# -----------------------------------------------------------------------------
# 生成报告
# -----------------------------------------------------------------------------
generate_report() {
    if [[ "$QUIET" == false ]]; then
        info "采集 CPU 快照并生成 HTML 报告..."
    fi

    cd "${ROOT}"
    uv run python scripts/cpu_report.py
}

# -----------------------------------------------------------------------------
# 停止压测
# -----------------------------------------------------------------------------
stop_stress() {
    if [[ "$MODE" == "report-only" ]]; then
        return 0
    fi

    if [[ "$QUIET" == false ]]; then
        info "停止压测进程..."
    fi

    # 停止 stress
    if [[ -n "${STRESS_PID:-}" ]]; then
        kill "$STRESS_PID" 2>/dev/null || true
        wait "$STRESS_PID" 2>/dev/null || true
    fi

    # 停止单个 dd
    if [[ -n "${DD_PID:-}" ]]; then
        kill "$DD_PID" 2>/dev/null || true
        wait "$DD_PID" 2>/dev/null || true
    fi

    # 停止多个 dd
    if [[ -n "${DD_PIDS:-}" ]]; then
        for pid in "${DD_PIDS[@]}"; do
            kill "$pid" 2>/dev/null || true
        done
        for pid in "${DD_PIDS[@]}"; do
            wait "$pid" 2>/dev/null || true
        done
    fi

    # 兜底清理
    pkill -f "dd if=/dev/zero of=/dev/null" 2>/dev/null || true
    pkill -f "stress --cpu" 2>/dev/null || true
}

# -----------------------------------------------------------------------------
# 主流程
# -----------------------------------------------------------------------------
main() {
    parse_args "$@"

    cd "${ROOT}"

    if [[ "$QUIET" == false ]]; then
        echo "========================================"
        echo "  🔧 CPU 压测工具 v2.0"
        echo "========================================"
        echo ""
    fi

    # 检查依赖
    check_requirements

    # 清理残留
    cleanup_previous

    # 启动压测
    start_stress

    # 等待升温
    wait_for_heat

    # 生成报告
    generate_report

    # 停止压测
    stop_stress

    if [[ "$QUIET" == false ]]; then
        echo ""
        echo "========================================"
        success "压测完成！"
        echo "========================================"
        echo ""
        echo "📋 报告位置: ${ROOT}/data/reports/cpu_report_*.html"
        echo "   用浏览器打开即可查看 CPU 快照"
        echo ""
        echo "💡 提示:"
        echo "   - 多核压测: bash scripts/stress_cpu.sh --multi"
        echo "   - 仅看报告: bash scripts/stress_cpu.sh --report-only"
        echo "   - 清理残留: bash scripts/cleanup_stress.sh"
        echo "========================================"
    fi
}

# 捕获中断信号，确保清理
trap stop_stress EXIT

main "$@"

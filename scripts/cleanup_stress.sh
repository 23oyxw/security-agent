#!/usr/bin/env bash
#===============================================================================
# CPU 压测进程清理工具 — 杀光失控的压测进程
#
# 使用场景：
#   - UI 打不开了 / 压测进程卡死 / 想快速清场
#   - 压测脚本异常退出后残留进程
#   - 多核压测后批量清理
#
# 用法：bash scripts/cleanup_stress.sh [--quiet]
#===============================================================================

set -eu

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

QUIET=false
if [[ "${1:-}" == "--quiet" || "${1:-}" == "-q" ]]; then
    QUIET=true
fi

info()  { [[ "$QUIET" == false ]] && echo -e "${BLUE}[INFO]${NC} $1" || true; }
warn()  { [[ "$QUIET" == false ]] && echo -e "${YELLOW}[WARN]${NC} $1" || true; }
success() { [[ "$QUIET" == false ]] && echo -e "${GREEN}[OK]${NC} $1" || true; }
error() { [[ "$QUIET" == false ]] && echo -e "${RED}[ERROR]${NC} $1" || true; }

# -----------------------------------------------------------------------------
# 清理函数
# -----------------------------------------------------------------------------
cleanup_dd() {
    local count=0
    local pids=""

    # 模式1: dd if=/dev/zero of=/dev/null
    pids=$(pgrep -f "dd if=/dev/zero of=/dev/null" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        count=$(echo "$pids" | wc -l)
        info "发现 $count 个 dd 压测进程 (if=/dev/zero of=/dev/null)"
        kill -TERM $pids 2>/dev/null || true
        sleep 0.5
        # 检查是否还有残留
        local left=$(pgrep -f "dd if=/dev/zero of=/dev/null" 2>/dev/null || true)
        if [[ -n "$left" ]]; then
            kill -9 $left 2>/dev/null || true
            warn "部分进程已强制终止 (SIGKILL)"
        else
            success "dd 压测进程已正常终止"
        fi
    fi

    # 模式2: dd if=/dev/zero bs=1M (新脚本使用的模式)
    pids=$(pgrep -f "dd if=/dev/zero bs=1M" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        count=$(echo "$pids" | wc -l)
        info "发现 $count 个 dd 进程 (bs=1M 模式)"
        kill -TERM $pids 2>/dev/null || true
        sleep 0.3
        kill -9 $(pgrep -f "dd if=/dev/zero bs=1M" 2>/dev/null || true) 2>/dev/null || true
        success "已清理"
    fi

    # 模式3: 纯 dd 命令（更宽松的匹配）
    pids=$(pgrep "^dd$" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        count=$(echo "$pids" | wc -l)
        info "发现 $count 个普通 dd 进程"
        # 检查 CPU 使用率高的 dd 进程（可能是在压测的）
        for pid in $pids; do
            if [[ -f "/proc/$pid/stat" ]]; then
                # 简单判断：运行时间较长的 dd 可能是压测
                local runtime=$(ps -p $pid -o time= 2>/dev/null | tr -d ' ' || echo "00:00")
                if [[ "$runtime" > "00:10" ]]; then
                    kill -TERM $pid 2>/dev/null || true
                fi
            fi
        done
        success "普通 dd 进程已处理"
    fi
}

cleanup_stress() {
    local count=0
    local pids=""

    # stress 压测工具
    pids=$(pgrep -f "^stress" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        count=$(echo "$pids" | wc -l)
        info "发现 $count 个 stress 进程"
        kill -TERM $pids 2>/dev/null || true
        sleep 0.5
        kill -9 $(pgrep -f "^stress" 2>/dev/null || true) 2>/dev/null || true
        success "stress 进程已清理"
    fi

    # timeout 包装的 stress
    pids=$(pgrep -f "timeout.*stress" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        info "发现 timeout+stress 组合进程"
        kill -TERM $pids 2>/dev/null || true
        sleep 0.3
        kill -9 $pids 2>/dev/null || true
        success "已清理"
    fi
}

cleanup_timeout_dd() {
    local pids=$(pgrep -f "timeout.*dd if=/dev/zero" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        info "发现 timeout+dd 组合进程"
        kill -TERM $pids 2>/dev/null || true
        sleep 0.3
        kill -9 $pids 2>/dev/null || true
        success "已清理 timeout+dd"
    fi
}

# -----------------------------------------------------------------------------
# 主流程
# -----------------------------------------------------------------------------
main() {
    if [[ "$QUIET" == false ]]; then
        echo "==========================================="
        echo "  🔧 CPU 压测进程清理工具"
        echo "==========================================="
        echo ""
    fi

    local found_any=false

    # 检查是否有任何压测进程
    if pgrep -f "dd if=/dev/zero" &>/dev/null || \
       pgrep -f "^stress" &>/dev/null || \
       pgrep -f "timeout.*dd" &>/dev/null; then
        found_any=true
    fi

    if [[ "$found_any" == false ]]; then
        if [[ "$QUIET" == false ]]; then
            success "未发现压测进程，系统干净"
        fi
        exit 0
    fi

    # 执行清理
    cleanup_dd
    cleanup_stress
    cleanup_timeout_dd

    # 最终检查
    sleep 0.5
    local remaining=$(pgrep -f "dd if=/dev/zero" 2>/dev/null || true)
    remaining+=" $(pgrep -f "^stress" 2>/dev/null || true)"

    if [[ "$QUIET" == false ]]; then
        echo ""
        if [[ -z "$(echo "$remaining" | tr -d ' ')" ]]; then
            echo "==========================================="
            success "清理完成！所有压测进程已终止"
            echo "==========================================="
        else
            echo "==========================================="
            warn "清理完成，但仍有部分进程残留"
            echo "剩余进程: $(echo "$remaining" | tr '\n' ' ')"
            echo "==========================================="
        fi
    fi
}

main "$@"

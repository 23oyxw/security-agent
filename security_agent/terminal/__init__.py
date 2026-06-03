"""Terminal 子系统 — 规则校验 + 最小权限代理执行 + 全链路追踪.

对外公开现有执行器接口，同时提供简明别名供新代码使用。
"""

from security_agent.terminal.executor import (
    TerminalResult,
    get_privilege_status,
    run_readonly,
    run_readonly_sync,
    run_terminal,
    run_terminal_sync,
)
from security_agent.terminal.privilege import (
    PrivilegeBroker,
    PrivilegeResult,
    get_privilege_broker,
)

# ---- 简明别名（新代码推荐使用） ----
execute = run_terminal_sync
safe_execute = run_readonly_sync
current_privilege = get_privilege_status
run_as_restricted = run_terminal_sync  # 受限执行即通过 PrivilegeBroker 降权，run_terminal_sync 已内置

__all__ = [
    # 核心执行器
    "TerminalResult",
    "run_terminal_sync",
    "run_terminal",
    "run_readonly_sync",
    "run_readonly",
    "get_privilege_status",
    # 权限代理
    "PrivilegeBroker",
    "PrivilegeResult",
    "get_privilege_broker",
    # 别名
    "execute",
    "safe_execute",
    "current_privilege",
    "run_as_restricted",
]

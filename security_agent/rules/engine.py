"""规则引擎 — 所有自主动作必须先过规则门."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionKind(str, Enum):
    TOOL = "tool"
    TERMINAL = "terminal"
    BLOCK = "block"


class RuleVerdict(str, Enum):
    ALLOW = "allow"
    NEED_CONFIRM = "confirm"
    DENY = "deny"


@dataclass
class RuleCheckResult:
    verdict: RuleVerdict
    reason: str
    rule_id: str = ""


# 禁止的终端模式（子串/正则）
TERMINAL_DENY_PATTERNS = [
    r"rm\s+-rf",
    r"mkfs",
    r"dd\s+if=",
    r">\s*/dev/",
    r"chmod\s+777",
    r"curl\s+.*\|\s*bash",
    r"wget\s+.*\|\s*sh",
    r":\(\)\s*\{",
    r"shutdown",
    r"reboot",
    r"init\s+0",
    r"passwd",
    r"userdel",
    r"iptables\s+-F",
]

# 允许的前缀（只读 / 观测类）
TERMINAL_ALLOW_PREFIXES = (
    "ps ",
    "ps aux",
    "pgrep ",
    "pidof ",
    "ss ",
    "netstat ",
    "ls ",
    "ls -",
    "cat ",
    "head ",
    "tail ",
    "grep ",
    "egrep ",
    "find ",
    "df ",
    "free ",
    "uptime",
    "whoami",
    "id",
    "uname",
    "hostname",
    "systemctl status",
    "journalctl ",
    "last ",
    "w",
    "top -bn1",
)

# 需用户确认才可执行的终端
TERMINAL_CONFIRM_PREFIXES = (
    "kill ",
    "pkill ",
    "sudo kill",
    "systemctl restart",
    "systemctl stop",
)

# root 写操作 / 提权变更 — 必须 UI 确认（只读 sudo 见下方前缀）
TERMINAL_ROOT_CONFIRM_PATTERNS = [
    r"\bsudo\s+(rm|chmod|chown|userdel|useradd|groupadd|usermod|passwd|iptables|mkfs|dd|tee|mv|cp)\b",
    r"\bsudo\s+systemctl\s+(restart|stop|disable|mask)",
    r"\bsu\s+-c\s+",
    r"\bchown\s+",
    r"\bchmod\s+[0-7]{3,4}\b",
    r"\buserdel\s+",
    r"\buseradd\s+",
    r"\bgroupadd\s+",
    r">\s*/etc/",
    r"\btee\s+/etc/",
]

# 允许的 root 只读观测（不需确认）
TERMINAL_ROOT_READ_PREFIXES = (
    "sudo systemctl status",
    "sudo cat ",
    "sudo ls ",
    "sudo ss ",
    "sudo journalctl ",
    "sudo head ",
    "sudo tail ",
    "sudo grep ",
)

# 工具分级
TOOLS_AUTO_OK = frozenset(
    {
        "query_security_scan",
        "query_security_scan_json",
        "list_processes",
        "get_process_detail",
        "generate_security_report",
        "start_monitor",
        "stop_monitor",
        "get_monitor_events",
        "get_audit_log",
        "get_system_health",
        "list_network_connections",
        "check_sensitive_paths",
        "run_full_security_check",
        "run_autonomous_mission",
        "run_risk_demo",
        "test_terminal_boundaries",
        "run_detection_calibration",
        "search_security_knowledge",
        "get_grounded_advice",
        "check_exposed_ports",
        "build_knowledge_index",
    }
)

TOOLS_NEED_CONFIRM = frozenset({"block_high_risk_process", "run_terminal_command"})


def check_terminal(command: str, *, user_confirmed: bool = False) -> RuleCheckResult:
    cmd = command.strip()
    if not cmd:
        return RuleCheckResult(RuleVerdict.DENY, "空命令", "T-EMPTY")

    lower = cmd.lower()

    for pat in TERMINAL_DENY_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            # sudo 下的账号变更走确认流，不直接 deny
            if pat in (r"userdel", r"passwd") and re.search(r"\bsudo\s+", cmd, re.IGNORECASE):
                break
            return RuleCheckResult(RuleVerdict.DENY, f"命令命中禁止规则: {pat}", "T-DENY")

    for prefix in TERMINAL_ROOT_READ_PREFIXES:
        if lower.startswith(prefix.lower()):
            return RuleCheckResult(RuleVerdict.ALLOW, "root 只读观测", "T-ROOT-READ")

    for pat in TERMINAL_ROOT_CONFIRM_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            if user_confirmed:
                return RuleCheckResult(RuleVerdict.ALLOW, "root 写操作已确认", "T-ROOT-OK")
            return RuleCheckResult(
                RuleVerdict.NEED_CONFIRM,
                "涉及 root 增删改或系统变更，须用户在界面确认",
                "T-ROOT-CONFIRM",
            )

    for prefix in TERMINAL_ALLOW_PREFIXES:
        if lower.startswith(prefix.lower()):
            return RuleCheckResult(RuleVerdict.ALLOW, "只读/观测命令", "T-ALLOW")

    for prefix in TERMINAL_CONFIRM_PREFIXES:
        if lower.startswith(prefix.lower()):
            if user_confirmed:
                return RuleCheckResult(RuleVerdict.ALLOW, "用户已确认", "T-CONFIRM-OK")
            return RuleCheckResult(
                RuleVerdict.NEED_CONFIRM,
                "终止/重启类命令需用户确认",
                "T-CONFIRM",
            )

    return RuleCheckResult(
        RuleVerdict.DENY,
        "命令不在白名单，仅允许观测类命令或已确认的高危命令",
        "T-NOT-ALLOWED",
    )


def check_tool(name: str, args: dict[str, Any] | None, *, user_confirmed: bool = False) -> RuleCheckResult:
    if name in TOOLS_AUTO_OK:
        return RuleCheckResult(RuleVerdict.ALLOW, "工具允许自动执行", "TOOL-AUTO")
    if name == "block_high_risk_process":
        if user_confirmed or (args or {}).get("force"):
            return RuleCheckResult(RuleVerdict.ALLOW, "拦截已授权", "TOOL-BLOCK-OK")
        return RuleCheckResult(RuleVerdict.NEED_CONFIRM, "拦截进程需确认", "TOOL-BLOCK")
    if name == "run_terminal_command":
        return check_terminal((args or {}).get("command", ""), user_confirmed=user_confirmed)
    return RuleCheckResult(RuleVerdict.DENY, f"未知工具: {name}", "TOOL-UNKNOWN")


def check_action(
    kind: ActionKind,
    payload: dict[str, Any],
    *,
    user_confirmed: bool = False,
) -> RuleCheckResult:
    if kind == ActionKind.TERMINAL:
        return check_terminal(payload.get("command", ""), user_confirmed=user_confirmed)
    if kind == ActionKind.TOOL:
        return check_tool(payload.get("name", ""), payload.get("args"), user_confirmed=user_confirmed)
    if kind == ActionKind.BLOCK:
        return check_tool("block_high_risk_process", payload, user_confirmed=user_confirmed)
    return RuleCheckResult(RuleVerdict.DENY, "未知动作类型", "UNK")

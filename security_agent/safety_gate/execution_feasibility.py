"""执行可行性 — 区分「安全评估通过」与「本机能否实际执行」."""

from __future__ import annotations

import platform
import re
from typing import Any

_LINUX_ONLY_HINTS: list[tuple[str, str]] = [
    (r"\bss\b", "ss 为 Linux 套接字统计工具"),
    (r"\bjournalctl\b", "journalctl 依赖 systemd"),
    (r"\bcrontab\b", "crontab 为 Linux 定时任务"),
    (r"/etc/cron", "/etc/cron 为 Linux cron 目录"),
    (r"/proc/", "/proc 为 Linux 伪文件系统"),
    (r"\bapt\b", "apt 为 Debian/Ubuntu 包管理器"),
    (r"\byum\b", "yum 为 RHEL 系包管理器"),
    (r"\bdf\b", "df 在 Windows 上输出格式不同"),
    (r"\bfree\b", "free 为 Linux 内存查看命令"),
    (r"2>/dev/null", "shell 重定向在 Windows cmd 中无效"),
    (r"\| head\b", "管道 head 在 Windows 上通常不可用"),
    (r"find / -perm", "全盘 find 为 Linux 权限排查语法"),
]


def check_execution_feasibility(command: str, *, target_type: str = "terminal") -> dict[str, Any]:
    sys_name = platform.system().lower()
    cmd = (command or "").strip()

    if target_type != "terminal" or not cmd:
        return {"ok": True, "platform": sys_name, "reason": "", "hint": ""}

    if sys_name != "windows":
        return {"ok": True, "platform": sys_name, "reason": "", "hint": ""}

    issues: list[str] = []
    for pattern, msg in _LINUX_ONLY_HINTS:
        if re.search(pattern, cmd, re.IGNORECASE):
            issues.append(msg)

    if issues:
        return {
            "ok": False,
            "platform": "windows",
            "reason": "；".join(dict.fromkeys(issues)),
            "hint": (
                "安全评估通过表示策略允许，不代表 Windows 本机可执行 Linux 运维命令。"
                "请在 Linux 主机、WSL 或演示环境执行，或改用 Windows 等价命令（如 netstat -ano）。"
            ),
        }

    return {"ok": True, "platform": "windows", "reason": "", "hint": ""}

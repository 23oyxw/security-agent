"""TerminalContext — 命令执行前的上下文自动采集.

设计原则（可解释 + 可追溯）:
    每次命令执行前，自动采集系统状态快照。
    这不是为了拦截，而是为了让后续的「为什么这条命令当时这样执行」可追溯。

采集维度:
    1. 系统状态   — cwd、用户、负载、可用内存、磁盘空间
    2. 会话状态   — 最近命令、最近输出、失败次数、会话时长
    3. 文件状态   — 最近修改的文件、当前打开的文件描述符
    4. 安全状态   — 安全闸门状态、未读告警数

用法:
    from security_agent.terminal.context import TerminalContext

    ctx = TerminalContext()
    snapshot = ctx.gather()
    # snapshot 可序列化，随 trace_id 存入审计日志
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False


@dataclass
class ContextSnapshot:
    """一次命令执行前的完整上下文快照."""

    # 系统状态
    cwd: str = ""
    current_user: str = ""
    hostname: str = ""
    platform: str = ""
    load_avg: str = ""            # "0.5 / 1.2 / 0.8" 或 "N/A"
    mem_available_mb: int = 0
    disk_free_mb: int = 0
    cpu_percent: float = 0.0

    # 会话状态
    recent_commands: list[str] = field(default_factory=list)   # 最近 5 条
    recent_outputs: list[str] = field(default_factory=list)    # 最近 5 条输出的摘要
    failed_count: int = 0                                       # 最近失败次数
    session_started_at: float = 0.0                             # 会话开始时间戳

    # 文件状态
    modified_files: list[str] = field(default_factory=list)    # 最近被修改的文件
    open_fd_count: int = 0                                      # 当前进程打开的文件描述符数

    # 安全状态
    safety_gate_ok: bool = True
    pending_alerts: int = 0

    # 元数据
    gathered_at: str = ""
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": {
                "cwd": self.cwd,
                "user": self.current_user,
                "hostname": self.hostname,
                "platform": self.platform,
                "load_avg": self.load_avg,
                "mem_available_mb": self.mem_available_mb,
                "disk_free_mb": self.disk_free_mb,
                "cpu_percent": self.cpu_percent,
            },
            "session": {
                "recent_commands": self.recent_commands[-5:],
                "failed_count": self.failed_count,
                "session_elapsed_sec": int(time.time() - self.session_started_at) if self.session_started_at else 0,
            },
            "files": {
                "recently_modified": self.modified_files[-10:],
                "open_fd_count": self.open_fd_count,
            },
            "security": {
                "safety_gate_ok": self.safety_gate_ok,
                "pending_alerts": self.pending_alerts,
            },
            "meta": {
                "gathered_at": self.gathered_at,
                "trace_id": self.trace_id,
            },
        }

    @property
    def summary(self) -> str:
        """人类可读的上下文摘要."""
        parts = [
            f"用户={self.current_user}",
            f"目录={self.cwd}",
            f"负载={self.load_avg}",
            f"可用内存={self.mem_available_mb}MB",
            f"磁盘={self.disk_free_mb}MB",
        ]
        if self.failed_count > 0:
            parts.append(f"最近失败={self.failed_count}次")
        if self.pending_alerts > 0:
            parts.append(f"未读告警={self.pending_alerts}")
        return " · ".join(parts)


class TerminalContext:
    """终端上下文采集器.

    单例模式，全局共享会话状态。
    """

    def __init__(self):
        self._session_start = time.time()
        self._command_history: list[str] = []
        self._output_history: list[str] = []
        self._failure_count = 0

    def gather(self, *, trace_id: str = "") -> ContextSnapshot:
        """采集当前时刻的完整上下文快照."""
        from security_agent.timeutil import now_iso

        snap = ContextSnapshot(
            cwd=os.getcwd(),
            current_user=self._whoami(),
            hostname=self._hostname(),
            platform=os.uname().sysname if hasattr(os, "uname") else os.name,
            load_avg=self._load_avg(),
            mem_available_mb=self._mem_available(),
            disk_free_mb=self._disk_free(),
            cpu_percent=self._cpu_percent(),
            recent_commands=list(self._command_history[-5:]),
            recent_outputs=list(self._output_history[-5:]),
            failed_count=self._failure_count,
            session_started_at=self._session_start,
            modified_files=self._recently_modified(),
            open_fd_count=self._open_fds(),
            safety_gate_ok=self._safety_gate_status(),
            pending_alerts=self._pending_alert_count(),
            gathered_at=now_iso(),
            trace_id=trace_id,
        )
        return snap

    # ---- 会话记录 ----

    def record_command(self, command: str) -> None:
        """记录一条已执行的命令."""
        self._command_history.append(command)
        if len(self._command_history) > 100:
            self._command_history = self._command_history[-100:]

    def record_output(self, output_summary: str) -> None:
        """记录一条命令的输出摘要（截断到 500 字符）."""
        self._output_history.append(output_summary[:500])
        if len(self._output_history) > 100:
            self._output_history = self._output_history[-100:]

    def record_failure(self) -> None:
        self._failure_count += 1

    def record_success(self) -> None:
        """成功后重置连续失败计数."""
        self._failure_count = 0

    @property
    def session_elapsed(self) -> float:
        return time.time() - self._session_start

    # ---- 私有采集方法 ----

    @staticmethod
    def _whoami() -> str:
        if HAS_PWD:
            try:
                return pwd.getpwuid(os.getuid()).pw_name
            except (KeyError, AttributeError):
                pass
        return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"

    @staticmethod
    def _hostname() -> str:
        import socket
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    @staticmethod
    def _load_avg() -> str:
        if HAS_PSUTIL:
            try:
                la = psutil.getloadavg()
                return " / ".join(f"{v:.1f}" for v in la)
            except (OSError, AttributeError):
                pass
        try:
            return os.read("/proc/loadavg", 20).decode().split()[0] if os.path.exists("/proc/loadavg") else "N/A"
        except Exception:
            pass
        return "N/A"

    @staticmethod
    def _mem_available() -> int:
        if HAS_PSUTIL:
            try:
                return int(psutil.virtual_memory().available / 1024 / 1024)
            except Exception:
                pass
        return 0

    @staticmethod
    def _disk_free() -> int:
        try:
            import shutil
            return int(shutil.disk_usage(os.getcwd()).free / 1024 / 1024)
        except Exception:
            return 0

    @staticmethod
    def _cpu_percent() -> float:
        if HAS_PSUTIL:
            try:
                return psutil.cpu_percent(interval=0.1)
            except Exception:
                pass
        return 0.0

    @staticmethod
    def _recently_modified() -> list[str]:
        """最近 5 分钟内修改的文件（最多 10 个）."""
        try:
            import time as _time
            now = _time.time()
            files = []
            cwd = Path(os.getcwd())
            for f in cwd.rglob("*"):
                if f.is_file():
                    try:
                        mtime = f.stat().st_mtime
                        if now - mtime < 300:  # 5 分钟
                            files.append(str(f.relative_to(cwd)))
                    except OSError:
                        pass
                if len(files) >= 10:
                    break
            return files
        except Exception:
            return []

    @staticmethod
    def _open_fds() -> int:
        if HAS_PSUTIL:
            try:
                return len(psutil.Process().open_files())
            except Exception:
                pass
        return 0

    @staticmethod
    def _safety_gate_status() -> bool:
        try:
            from security_agent.safety_gate.gate import SafetyGate
            return SafetyGate().status().get("ok", True)
        except Exception:
            return True

    @staticmethod
    def _pending_alert_count() -> int:
        try:
            from security_agent.notify.alerts import get_unread_count
            return get_unread_count()
        except Exception:
            return 0


# 全局单例
_context: TerminalContext | None = None


def get_terminal_context() -> TerminalContext:
    global _context
    if _context is None:
        _context = TerminalContext()
    return _context

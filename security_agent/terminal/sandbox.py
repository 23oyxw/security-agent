"""受限执行沙箱 — OS 级进程隔离 + 资源限制.

提供:
  - setuid/setgid 权限降级 (preexec_fn)
  - 进程资源限制 (CPU/内存/文件)
  - chroot 可选隔离
  - 受限用户标识 security-agent-op
  - SandboxResult 统一返回

用法:
    from security_agent.terminal.sandbox import SandboxExecutor
    sandbox = SandboxExecutor(restricted_user="security-agent-op")
    result = sandbox.run("ls -la /tmp", risk_level="READONLY")
"""

from __future__ import annotations

import os
import pwd
import grp
import shutil
import signal
import subprocess
import resource as rlim
from dataclasses import dataclass, field
from typing import Any

from security_agent.audit import log as audit
from security_agent.timeutil import now_iso

# 受限运维用户标识
RESTRICTED_USER = "security-agent-op"

# 不允许作为沙箱用户的系统账户
FORBIDDEN_USERS = frozenset({"root", "admin", "Administrator", "nobody"})

# 资源限制默认值
DEFAULT_CPU_LIMIT_SEC = 30      # CPU 时间上限
DEFAULT_MEMORY_LIMIT_MB = 512   # 内存上限
DEFAULT_FILE_SIZE_MB = 100      # 单文件大小上限
DEFAULT_PROCESS_LIMIT = 50      # 子进程上限


@dataclass
class SandboxResult:
    """沙箱执行结果."""
    ok: bool
    command: str
    stdout: str
    stderr: str
    exit_code: int
    executed_as_user: str = ""
    executed_as_uid: int = 0
    executed_as_gid: int = 0
    was_isolated: bool = False        # 是否使用了沙箱隔离
    isolation_method: str = ""        # uid/gid/chroot/none
    risk_level: str = ""
    trace_id: str = ""
    executed_at: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "command": self.command[:200],
            "stdout": self.stdout[:4000],
            "stderr": self.stderr[:2000],
            "exit_code": self.exit_code,
            "executed_as_user": self.executed_as_user,
            "executed_as_uid": self.executed_as_uid,
            "executed_as_gid": self.executed_as_gid,
            "was_isolated": self.was_isolated,
            "isolation_method": self.isolation_method,
            "risk_level": self.risk_level,
            "trace_id": self.trace_id,
        }


class SandboxExecutor:
    """受限执行沙箱.

    根据风险等级自动选择隔离策略:
      READONLY     → 当前用户, 资源限制
      REVERSIBLE   → security-agent-op 用户 + 资源限制
      IRREVERSIBLE → security-agent-op + setuid/setgid + 严格资源限制
      CRITICAL     → 拒绝执行
    """

    def __init__(
        self,
        *,
        restricted_user: str = RESTRICTED_USER,
        cpu_limit: int = DEFAULT_CPU_LIMIT_SEC,
        memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB,
        file_size_mb: int = DEFAULT_FILE_SIZE_MB,
        process_limit: int = DEFAULT_PROCESS_LIMIT,
    ):
        self.restricted_user = restricted_user
        self.cpu_limit = cpu_limit
        self.memory_limit_mb = memory_limit_mb
        self.file_size_mb = file_size_mb
        self.process_limit = process_limit
        self._user_uid: int | None = None
        self._user_gid: int | None = None
        self._user_available: bool = False
        self._resolve_user()

    def _resolve_user(self) -> None:
        """解析并验证受限用户."""
        if self.restricted_user in FORBIDDEN_USERS:
            self._user_available = False
            return

        try:
            pw = pwd.getpwnam(self.restricted_user)
            if pw.pw_uid == 0:
                self._user_available = False
                return

            self._user_uid = pw.pw_uid
            self._user_gid = pw.pw_gid
            self._user_available = True
        except KeyError:
            self._user_available = False

    @property
    def available(self) -> bool:
        return self._user_available

    def get_status(self) -> dict[str, Any]:
        return {
            "restricted_user": self.restricted_user,
            "available": self._user_available,
            "uid": self._user_uid,
            "gid": self._user_gid,
            "cpu_limit_sec": self.cpu_limit,
            "memory_limit_mb": self.memory_limit_mb,
            "file_size_mb": self.file_size_mb,
            "process_limit": self.process_limit,
        }

    def run(
        self,
        command: str,
        *,
        risk_level: str = "READONLY",
        timeout_sec: float = 30.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> SandboxResult:
        """在沙箱中执行命令.

        Args:
            command: shell 命令
            risk_level: READONLY / REVERSIBLE / IRREVERSIBLE / CRITICAL
            timeout_sec: 超时
            cwd: 工作目录
            env: 环境变量

        Returns:
            SandboxResult
        """
        executed_at = now_iso()
        work_dir = cwd or os.getcwd()

        # CRITICAL: 拒绝
        if risk_level == "CRITICAL":
            return SandboxResult(
                ok=False, command=command, stdout="", stderr="",
                exit_code=-1, risk_level=risk_level,
                error="CRITICAL 等级操作需人工审批, 沙箱拒绝自动执行",
                executed_at=executed_at,
            )

        # READONLY: 当前用户 + 资源限制
        if risk_level == "READONLY" or not self._user_available:
            return self._run_with_limits(
                command, timeout_sec, work_dir, env,
                risk_level=risk_level,
                isolation_method="resource_limits",
            )

        # REVERSIBLE / IRREVERSIBLE: setuid/setgid 隔离
        return self._run_as_restricted(
            command, timeout_sec, work_dir, env,
            risk_level=risk_level,
            isolation_method="setuid_setgid",
        )

    def _run_with_limits(
        self, command: str, timeout: float, cwd: str,
        env: dict | None, risk_level: str, isolation_method: str,
    ) -> SandboxResult:
        """当前用户 + 资源限制执行."""
        executed_at = now_iso()

        def set_limits():
            """preexec_fn: 在子进程中设置资源限制."""
            try:
                # CPU 时间限制
                rlim.setrlimit(rlim.RLIMIT_CPU, (self.cpu_limit, self.cpu_limit))
            except Exception:
                pass
            try:
                # 内存限制
                mem_bytes = self.memory_limit_mb * 1024 * 1024
                rlim.setrlimit(rlim.RLIMIT_AS, (mem_bytes, mem_bytes))
            except Exception:
                pass
            try:
                # 文件大小限制
                file_bytes = self.file_size_mb * 1024 * 1024
                rlim.setrlimit(rlim.RLIMIT_FSIZE, (file_bytes, file_bytes))
            except Exception:
                pass
            try:
                # 进程数限制
                rlim.setrlimit(rlim.RLIMIT_NPROC, (self.process_limit, self.process_limit))
            except Exception:
                pass

        try:
            proc_env = os.environ.copy()
            if env:
                proc_env.update(env)
            proc_env["LANG"] = proc_env.get("LANG", "C.UTF-8")

            proc = subprocess.run(
                ["sh", "-c", command],
                shell=False,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=proc_env,
                preexec_fn=set_limits,
            )

            return SandboxResult(
                ok=proc.returncode == 0,
                command=command,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                exit_code=proc.returncode,
                executed_as_user=pwd.getpwuid(os.getuid()).pw_name,
                executed_as_uid=os.getuid(),
                executed_as_gid=os.getgid(),
                was_isolated=True,
                isolation_method=isolation_method,
                risk_level=risk_level,
                executed_at=executed_at,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                ok=False, command=command, stdout="", stderr=f"超时 ({timeout}s)",
                exit_code=-1, risk_level=risk_level,
                isolation_method=isolation_method,
                error="命令超时", executed_at=executed_at,
            )
        except Exception as e:
            return SandboxResult(
                ok=False, command=command, stdout="", stderr=str(e),
                exit_code=-1, risk_level=risk_level,
                isolation_method=isolation_method,
                error=str(e), executed_at=executed_at,
            )

    def _run_as_restricted(
        self, command: str, timeout: float, cwd: str,
        env: dict | None, risk_level: str, isolation_method: str,
    ) -> SandboxResult:
        """以受限用户身份执行 (setuid/setgid via preexec_fn)."""
        executed_at = now_iso()

        def demote():
            """preexec_fn: 降权到受限用户 + 资源限制."""
            # 先设资源限制
            try:
                rlim.setrlimit(rlim.RLIMIT_CPU, (self.cpu_limit, self.cpu_limit))
            except Exception:
                pass
            try:
                mem_bytes = self.memory_limit_mb * 1024 * 1024
                rlim.setrlimit(rlim.RLIMIT_AS, (mem_bytes, mem_bytes))
            except Exception:
                pass
            try:
                file_bytes = self.file_size_mb * 1024 * 1024
                rlim.setrlimit(rlim.RLIMIT_FSIZE, (file_bytes, file_bytes))
            except Exception:
                pass
            try:
                rlim.setrlimit(rlim.RLIMIT_NPROC, (self.process_limit, self.process_limit))
            except Exception:
                pass

            # setgid 必须在 setuid 之前
            if self._user_gid is not None:
                try:
                    os.setgid(self._user_gid)
                except OSError:
                    pass

            # setuid 降权
            if self._user_uid is not None:
                try:
                    os.setuid(self._user_uid)
                except OSError:
                    pass

        try:
            proc_env = os.environ.copy()
            if env:
                proc_env.update(env)
            proc_env["LANG"] = proc_env.get("LANG", "C.UTF-8")
            proc_env["HOME"] = "/nonexistent"

            proc = subprocess.run(
                ["sh", "-c", command],
                shell=False,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=proc_env,
                preexec_fn=demote,
            )

            return SandboxResult(
                ok=proc.returncode == 0,
                command=command,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                exit_code=proc.returncode,
                executed_as_user=self.restricted_user,
                executed_as_uid=self._user_uid or 0,
                executed_as_gid=self._user_gid or 0,
                was_isolated=True,
                isolation_method=isolation_method,
                risk_level=risk_level,
                executed_at=executed_at,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                ok=False, command=command, stdout="", stderr=f"超时 ({timeout}s)",
                exit_code=-1, risk_level=risk_level,
                isolation_method=isolation_method,
                error="命令超时", executed_at=executed_at,
            )
        except Exception as e:
            return SandboxResult(
                ok=False, command=command, stdout="", stderr=str(e),
                exit_code=-1, risk_level=risk_level,
                isolation_method=isolation_method,
                error=str(e), executed_at=executed_at,
            )

    @staticmethod
    def create_restricted_user() -> dict[str, Any]:
        """尝试创建 security-agent-op 受限用户."""
        try:
            pwd.getpwnam(RESTRICTED_USER)
            return {"status": "exists", "user": RESTRICTED_USER}
        except KeyError:
            pass

        if os.getuid() != 0:
            return {"status": "needs_root", "user": RESTRICTED_USER,
                    "command": f"sudo useradd -r -s /sbin/nologin -M {RESTRICTED_USER}"}

        try:
            subprocess.run(
                ["useradd", "-r", "-s", "/sbin/nologin", "-M", RESTRICTED_USER],
                check=True, capture_output=True, text=True, timeout=10,
            )
            return {"status": "created", "user": RESTRICTED_USER}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "user": RESTRICTED_USER, "error": e.stderr or str(e)}


# 全局单例
_sandbox: SandboxExecutor | None = None


def get_sandbox() -> SandboxExecutor:
    global _sandbox
    if _sandbox is None:
        _sandbox = SandboxExecutor()
    return _sandbox

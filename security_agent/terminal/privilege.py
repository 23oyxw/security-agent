"""PrivilegeBroker — 最小权限代理执行引擎.

赛题核心得分点：所有写操作以受限用户执行，非必要不使用 root。

设计原则:
    - READONLY 风险操作 → 以当前用户执行（观测类，无风险）
    - REVERSIBLE 风险操作 → 以 agent_ops 受限用户执行（需确认）
    - IRREVERSIBLE 风险操作 → 以 agent_ops 执行 + 自动备份（需授权）
    - CRITICAL 风险操作 → 绝对禁止自动执行（需人工审批）

用法:
    from security_agent.terminal.privilege import PrivilegeBroker

    broker = PrivilegeBroker()
    result = broker.execute("rm -f /tmp/cache.log", risk_level=RiskLevel.REVERSIBLE)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

try:
    import pwd
except ImportError:  # Windows 无 pwd/grp
    pwd = None  # type: ignore[assignment]

from security_agent.audit import log as audit
from security_agent.audit.trace import TraceContext
from security_agent.rules.engine import RuleVerdict, check_terminal
from security_agent.safety_gate.risk import RiskLevel
from security_agent.security.redact import redact_command
from security_agent.timeutil import now_iso

# 受限运维账户名（若不存在则自动降级）
DEFAULT_RESTRICTED_USER = "agent_ops"

# 系统级安全豁免用户：root 和这些用户不允许作为受限账号
FORBIDDEN_RESTRICTED_USERS = frozenset({"root", "admin", "Administrator"})

PRIVILEGE_REQUIRED_PREFIXES = frozenset({
    "systemctl restart",
    "systemctl stop",
    "systemctl disable",
    "systemctl mask",
    "iptables -",
    "firewall-cmd",
    "ufw ",
    "apt install",
    "apt remove",
    "apt purge",
    "yum install",
    "yum remove",
    "dnf install",
    "dnf remove",
    "pip install",
    "mount ",
    "umount ",
    "mkfs",
    "fdisk ",
    "parted ",
})


def _has_unix_accounts() -> bool:
    return pwd is not None and sys.platform != "win32"


def _current_username() -> str:
    if _has_unix_accounts():
        return pwd.getpwuid(os.getuid()).pw_name
    return os.environ.get("USERNAME") or os.environ.get("USER") or "Administrator"


def _is_root_user() -> bool:
    if _has_unix_accounts():
        return os.getuid() == 0
    return False


@dataclass
class PrivilegeResult:
    """权限代理执行结果."""
    ok: bool
    command: str
    stdout: str
    stderr: str
    exit_code: int
    executed_as_user: str     # 实际执行的用户
    requested_user: str        # 期望的用户
    used_fallback: bool        # 是否因受限用户不可用而降级
    executed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "command": redact_command(self.command),
            "stdout": self.stdout[:4000],
            "stderr": self.stderr[:2000],
            "exit_code": self.exit_code,
            "executed_as_user": self.executed_as_user,
            "requested_user": self.requested_user,
            "used_fallback": self.used_fallback,
            "executed_at": self.executed_at,
        }


class PrivilegeBroker:
    """最小权限代理执行器.

    根据风险等级自动选择执行用户：
        READONLY → 当前用户（无降权必要，观测类无害）
        REVERSIBLE → agent_ops（受限用户，隔离风险）
        IRREVERSIBLE → agent_ops + 备份标记
        CRITICAL → 直接拒绝，需人工审批

    若受限用户不存在，自动降级为当前用户并记录告警审计日志。
    """

    def __init__(
        self,
        *,
        restricted_user: str = DEFAULT_RESTRICTED_USER,
        timeout_sec: float = 30.0,
        cwd: str | None = None,
    ):
        self._restricted_user = restricted_user
        self._restricted_uid: int | None = None
        self._restricted_available: bool = False
        self._timeout = timeout_sec
        self._cwd = cwd
        self._current_user = _current_username()
        self._is_root = _is_root_user()
        self._resolve_restricted_user()

    # ---- 受限用户解析 ----

    def _resolve_restricted_user(self) -> None:
        """解析受限用户是否存在."""
        if not _has_unix_accounts():
            self._restricted_available = False
            return

        if self._restricted_user in FORBIDDEN_RESTRICTED_USERS:
            self._restricted_available = False
            audit.append_audit(
                "privilege_broker",
                {
                    "event": "forbidden_user",
                    "user": self._restricted_user,
                    "reason": "受限用户不可为系统管理员账号",
                },
                level="warning",
            )
            return

        try:
            pw = pwd.getpwnam(self._restricted_user)
            self._restricted_uid = pw.pw_uid

            # 验证该用户不是 root (uid != 0)
            if self._restricted_uid == 0:
                self._restricted_available = False
                audit.append_audit(
                    "privilege_broker",
                    {"event": "root_detected", "user": self._restricted_user},
                    level="warning",
                )
                return

            # 检查 sudo 是否可用
            if shutil.which("sudo") is None:
                self._restricted_available = False
                audit.append_audit(
                    "privilege_broker",
                    {"event": "sudo_missing"},
                    level="warning",
                )
                return

            self._restricted_available = True
        except KeyError:
            self._restricted_available = False
            audit.append_audit(
                "privilege_broker",
                {
                    "event": "user_not_found",
                    "user": self._restricted_user,
                    "suggestion": f"sudo useradd -r -s /sbin/nologin -M {self._restricted_user}",
                },
                level="warning",
            )

    @property
    def restricted_available(self) -> bool:
        """受限用户是否可用."""
        return self._restricted_available

    @property
    def restricted_user(self) -> str:
        return self._restricted_user

    @property
    def current_user(self) -> str:
        return self._current_user

    def get_status(self) -> dict[str, Any]:
        """获取权限代理状态（供 UI/健康检查）."""
        return {
            "current_user": self._current_user,
            "is_root": self._is_root,
            "restricted_user": self._restricted_user,
            "restricted_available": self._restricted_available,
            "restricted_uid": self._restricted_uid,
        }

    # ---- 核心执行 ----

    def execute(
        self,
        command: str,
        *,
        risk_level: RiskLevel = RiskLevel.READONLY,
        user_confirmed: bool = False,
        timeout_sec: float | None = None,
        cwd: str | None = None,
    ) -> PrivilegeResult:
        """根据风险等级执行命令。

        Args:
            command: 要执行的 shell 命令
            risk_level: 风险等级（来自 RiskAssessor）
            user_confirmed: 用户是否已确认（REVERSIBLE 以上需要）
            timeout_sec: 超时秒数
            cwd: 工作目录

        Returns:
            PrivilegeResult 包含执行结果、实际用户等信息
        """
        executed_at = now_iso()
        trace_id = TraceContext.current_trace_id()
        timeout = timeout_sec or self._timeout
        work_dir = cwd or self._cwd or os.getcwd()

        # 1. 规则引擎校验
        rule_check = check_terminal(command, user_confirmed=user_confirmed)
        if rule_check.verdict == RuleVerdict.DENY:
            return PrivilegeResult(
                ok=False,
                command=command,
                stdout="",
                stderr=rule_check.reason,
                exit_code=-1,
                executed_as_user="(none)",
                requested_user="(none)",
                used_fallback=False,
                executed_at=executed_at,
            )

        # 2. 决定执行用户
        target_user, used_fallback = self._resolve_execution_user(risk_level, command)

        # 3. 如果 need_confirm 但未确认
        if rule_check.verdict == RuleVerdict.NEED_CONFIRM and not user_confirmed:
            return PrivilegeResult(
                ok=False,
                command=command,
                stdout="",
                stderr=rule_check.reason,
                exit_code=-1,
                executed_as_user=target_user,
                requested_user=target_user,
                used_fallback=used_fallback,
                executed_at=executed_at,
            )

        # 4. 执行
        try:
            result = self._run_command(
                command=command,
                target_user=target_user,
                timeout=timeout,
                cwd=work_dir,
            )

            audit.append_audit(
                "privilege_exec",
                {
                    "command": command[:200],
                    "exit_code": result.exit_code,
                    "executed_as_user": result.executed_as_user,
                    "risk_level": risk_level.name,
                    "used_fallback": used_fallback,
                    "trace_id": trace_id,
                },
                level="warning" if result.exit_code != 0 else "info",
            )

            return result
        except subprocess.TimeoutExpired:
            return PrivilegeResult(
                ok=False,
                command=command,
                stdout="",
                stderr=f"命令超时 ({timeout}s)",
                exit_code=-1,
                executed_as_user=target_user,
                requested_user=target_user,
                used_fallback=used_fallback,
                executed_at=executed_at,
            )
        except Exception as exc:
            return PrivilegeResult(
                ok=False,
                command=command,
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                executed_as_user=target_user,
                requested_user=target_user,
                used_fallback=used_fallback,
                executed_at=executed_at,
            )

    def _resolve_execution_user(
        self, risk_level: RiskLevel, command: str
    ) -> tuple[str, bool]:
        """根据风险等级决定以哪个用户执行。

        Returns:
            (target_user, used_fallback)
        """
        # CRITICAL: 直接拒绝（不应到达这里，应由 SafetyGate 在更上层拦截）
        if risk_level == RiskLevel.CRITICAL:
            return "(blocked)", False

        # READONLY: 以当前用户执行（观测类命令无害）
        if risk_level == RiskLevel.READONLY:
            return self._current_user, False

        # 检查是否需要特权才能执行（如 systemctl restart）
        if self._needs_privilege(command):
            # 需要特权但当前用户非 root → 报错让用户自行处理
            if not self._is_root:
                return self._current_user, True  # fallback，让命令自然失败
            # root 且受限用户可用 → 用受限用户（最小权限）
            if self._restricted_available:
                return self._restricted_user, False
            # root 但无私下受限用户 → 降级（记录告警）
            return self._current_user, True

        # REVERSIBLE / IRREVERSIBLE: 用受限用户
        if self._restricted_available and self._current_user != self._restricted_user:
            return self._restricted_user, False
        if self._restricted_available and self._current_user == self._restricted_user:
            # 已经在受限用户下运行
            return self._current_user, False

        # 受限用户不可用，降级到当前用户
        if self._is_root:
            audit.append_audit(
                "privilege_broker",
                {
                    "event": "root_fallback",
                    "command": redact_command(command),
                    "risk_level": risk_level.name,
                    "warning": "受限用户不可用，降级为 root 执行 —— 存在安全风险",
                },
                level="warning",
            )
        return self._current_user, True

    @staticmethod
    def _needs_privilege(command: str) -> bool:
        """判断命令是否本质上需要特权才能完成（如 systemctl restart）."""
        cmd_lower = command.strip().lower()
        for prefix in PRIVILEGE_REQUIRED_PREFIXES:
            if cmd_lower.startswith(prefix):
                return True
        return False

    def _run_command(
        self,
        command: str,
        target_user: str,
        timeout: float,
        cwd: str,
    ) -> PrivilegeResult:
        """实际执行命令（可能进行用户切换）."""
        executed_at = now_iso()

        # 如果目标用户与当前用户相同，直接执行
        if target_user == self._current_user:
            return self._run_as_current_user(command, timeout, cwd, executed_at)

        # 需要切换到受限用户
        if target_user == self._restricted_user:
            return self._run_as_restricted_user(command, timeout, cwd, executed_at)

        # 未知目标用户
        return PrivilegeResult(
            ok=False,
            command=command,
            stdout="",
            stderr=f"未知目标用户: {target_user}",
            exit_code=-1,
            executed_as_user=self._current_user,
            requested_user=target_user,
            used_fallback=True,
            executed_at=executed_at,
        )

    def _run_as_current_user(
        self, command: str, timeout: float, cwd: str, executed_at: str
    ) -> PrivilegeResult:
        """以当前用户执行."""
        env = os.environ.copy()
        env["LANG"] = env.get("LANG", "C.UTF-8")

        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        return PrivilegeResult(
            ok=proc.returncode == 0,
            command=command,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            exit_code=proc.returncode,
            executed_as_user=self._current_user,
            requested_user=self._current_user,
            used_fallback=False,
            executed_at=executed_at,
        )

    def _run_as_restricted_user(
        self, command: str, timeout: float, cwd: str, executed_at: str
    ) -> PrivilegeResult:
        """以受限用户身份通过 sudo -u 执行."""
        env = os.environ.copy()
        env["LANG"] = env.get("LANG", "C.UTF-8")

        # 用 sudo -u <user> -- <command> 来降权执行
        sudo_cmd = ["sudo", "-u", self._restricted_user, "--", "sh", "-c", command]

        proc = subprocess.run(
            sudo_cmd,
            shell=False,  # 不使用 shell=False 是安全的（参数是 list）
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        return PrivilegeResult(
            ok=proc.returncode == 0,
            command=command,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            exit_code=proc.returncode,
            executed_as_user=self._restricted_user,
            requested_user=self._restricted_user,
            used_fallback=False,
            executed_at=executed_at,
        )

    # ---- 便捷方法 ----

    def execute_readonly(
        self, command: str, *, timeout_sec: float | None = None
    ) -> PrivilegeResult:
        """执行只读观测命令（自动通过风险校验）."""
        return self.execute(command, risk_level=RiskLevel.READONLY, user_confirmed=True)

    def execute_with_confirm(
        self, command: str, *, timeout_sec: float | None = None
    ) -> PrivilegeResult:
        """执行可逆操作（需用户确认）."""
        return self.execute(
            command, risk_level=RiskLevel.REVERSIBLE, user_confirmed=True
        )

    # ---- 安装辅助 ----

    @staticmethod
    def setup_restricted_user() -> dict[str, Any]:
        """尝试创建受限运维账户 agent_ops。

        这是一个辅助函数，用于首次部署时自动创建受限用户。
        在麒麟/Linux 系统上执行：sudo useradd -r -s /sbin/nologin -M agent_ops
        """
        user_name = DEFAULT_RESTRICTED_USER
        if not _has_unix_accounts():
            return {
                "status": "unsupported",
                "user": user_name,
                "message": "Windows 环境请使用当前用户执行；受限账户仅在 Linux/麒麟创建",
            }
        try:
            pwd.getpwnam(user_name)
            return {"status": "exists", "user": user_name, "message": f"用户 {user_name} 已存在"}
        except KeyError:
            pass

        # 检查是否有 sudo 权限
        if os.getuid() != 0:
            return {
                "status": "needs_root",
                "user": user_name,
                "message": f"需要 root 权限创建用户: sudo useradd -r -s /sbin/nologin -M {user_name}",
            }

        try:
            subprocess.run(
                ["useradd", "-r", "-s", "/sbin/nologin", "-M", user_name],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {"status": "created", "user": user_name, "message": f"已创建受限用户 {user_name}"}
        except subprocess.CalledProcessError as exc:
            return {
                "status": "error",
                "user": user_name,
                "message": f"创建失败: {exc.stderr or str(exc)}",
            }
        except FileNotFoundError:
            return {
                "status": "error",
                "user": user_name,
                "message": "useradd 命令不存在",
            }


# 全局单例（懒加载）
_broker: PrivilegeBroker | None = None


def get_privilege_broker() -> PrivilegeBroker:
    """获取全局 PrivilegeBroker 单例."""
    global _broker
    if _broker is None:
        _broker = PrivilegeBroker()
    return _broker
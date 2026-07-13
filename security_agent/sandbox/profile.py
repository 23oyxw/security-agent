"""SandboxProfile — 根据风险等级自动选择隔离层数.

设计原则（可解释）:
    每个 Profile 的选择都有明确理由（reason），
    用户可以理解「为什么这条命令用这层隔离」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SandboxProfile:
    """一条沙箱隔离配置 — 定义了对某类操作施加哪些保护层.

    不可变：一次执行绑定一个 Profile，事后可审计。
    """

    name: str
    risk_level: str  # READONLY | REVERSIBLE | IRREVERSIBLE | CRITICAL

    # 各层开关
    setuid_enabled: bool = False
    rlimit_enabled: bool = True
    overlay_enabled: bool = False         # OverlayFS 写时复制
    mount_ns_enabled: bool = False        # mount namespace 隔离
    network_ns_enabled: bool = False      # network namespace 隔离 (P1)
    seccomp_enabled: bool = False         # seccomp-bpf 过滤 (P1)
    cgroup_enabled: bool = False          # cgroup v2 控制 (P1)

    # 资源限制参数
    cpu_limit_sec: int = 30
    memory_limit_mb: int = 512
    file_size_mb: int = 100
    process_limit: int = 50
    timeout_sec: float = 30.0

    # 可解释性
    reason: str = ""

    @property
    def layer_count(self) -> int:
        """实际启用的隔离层数."""
        layers = [
            self.setuid_enabled,
            self.rlimit_enabled,
            self.overlay_enabled,
            self.mount_ns_enabled,
            self.network_ns_enabled,
            self.seccomp_enabled,
            self.cgroup_enabled,
        ]
        return sum(1 for l in layers if l)

    @property
    def description(self) -> str:
        """人类可读的保护摘要."""
        parts = []
        if self.setuid_enabled:
            parts.append("用户降级")
        if self.rlimit_enabled:
            parts.append(f"资源限制(CPU={self.cpu_limit_sec}s/MEM={self.memory_limit_mb}MB)")
        if self.overlay_enabled:
            parts.append("写时复制(OverlayFS)")
        if self.mount_ns_enabled:
            parts.append("挂载隔离")
        if self.network_ns_enabled:
            parts.append("网络隔离")
        if self.seccomp_enabled:
            parts.append("系统调用过滤")
        if self.cgroup_enabled:
            parts.append("cgroup 管控")
        return " + ".join(parts) if parts else "无隔离(当前用户直接执行)"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "risk_level": self.risk_level,
            "layer_count": self.layer_count,
            "description": self.description,
            "reason": self.reason,
            "layers": {
                "setuid": self.setuid_enabled,
                "rlimit": self.rlimit_enabled,
                "overlay": self.overlay_enabled,
                "mount_ns": self.mount_ns_enabled,
                "network_ns": self.network_ns_enabled,
                "seccomp": self.seccomp_enabled,
                "cgroup": self.cgroup_enabled,
            },
            "limits": {
                "cpu_sec": self.cpu_limit_sec,
                "memory_mb": self.memory_limit_mb,
                "file_size_mb": self.file_size_mb,
                "process_limit": self.process_limit,
                "timeout_sec": self.timeout_sec,
            },
        }

    @classmethod
    def choose(cls, risk_level: str, *, command_type: str = "", is_linux: bool = True) -> "SandboxProfile":
        """根据风险等级自动选择隔离 Profile.

        选择逻辑（可解释）:
            READONLY     → 只观测，不加隔离（仅 rlimit 防资源耗尽）
            REVERSIBLE   → 可逆操作，加 OverlayFS（可回滚）
            IRREVERSIBLE → 不可逆操作，加 OverlayFS + mount ns（最严）
            CRITICAL     → 拒绝自动执行

        Args:
            risk_level: READONLY / REVERSIBLE / IRREVERSIBLE / CRITICAL
            command_type: 命令类型提示（观测/修改/删除/网络/权限）
            is_linux: 是否 Linux 环境（Windows 下 OverlayFS/namespace 不可用）
        """
        if risk_level == "CRITICAL":
            return cls(
                name="deny_critical",
                risk_level="CRITICAL",
                rlimit_enabled=False,
                reason="CRITICAL 等级操作需人工审批，沙箱拒绝自动执行",
            )

        if risk_level == "READONLY":
            return cls(
                name="observe_only",
                risk_level="READONLY",
                rlimit_enabled=True,
                cpu_limit_sec=15,
                memory_limit_mb=256,
                reason="只读观测命令，仅限制资源防止耗尽，不隔离文件系统",
            )

        if risk_level == "REVERSIBLE":
            return cls(
                name="safe_reversible",
                risk_level="REVERSIBLE",
                rlimit_enabled=True,
                overlay_enabled=is_linux,       # Linux: 写时复制，可秒级回滚
                mount_ns_enabled=False,          # P1 启用
                cpu_limit_sec=30,
                memory_limit_mb=512,
                reason="可逆操作：OverlayFS 写时复制保护原始文件，执行后可一键回滚（零成本）",
            )

        # IRREVERSIBLE
        return cls(
            name="strict_irreversible",
            risk_level="IRREVERSIBLE",
            setuid_enabled=True,                 # 降权用户
            rlimit_enabled=True,
            overlay_enabled=is_linux,
            mount_ns_enabled=is_linux,           # 隔离 /tmp、/proc
            cpu_limit_sec=60,
            memory_limit_mb=256,
            reason="不可逆操作：降权用户 + OverlayFS 写时复制 + 挂载命名空间隔离，多层次纵深防御",
        )

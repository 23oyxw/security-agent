"""Kylin MAC Checker — 麒麟操作系统强制访问控制集成.

在 MCP 工具执行前校验 SELinux/KYSEC 安全上下文，确保 AI 操作不越权.

支持:
  - SELinux (getenforce + context 匹配)
  - KYSEC (麒麟安全模块 kysec 标签)
  - 非麒麟环境优雅降级 (allowed=True, 不阻断)
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class MacCheckResult:
    """MAC 检查结果."""
    allowed: bool
    context_before: str = ""
    context_after: str = ""
    kysec_label: str = ""
    reason: str = ""
    enforcing: bool = False
    platform: str = "unknown"
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "allowed": self.allowed,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "kysec_label": self.kysec_label,
            "reason": self.reason,
            "enforcing": self.enforcing,
            "platform": self.platform,
        }


class KylinMACChecker:
    """麒麟强制访问控制检查器.

    在 MCP 工具执行前调用，校验进程安全上下文与目标资源是否兼容.
    """

    def __init__(self, enforce: bool = True):
        self.enforce = enforce
        self._selinux_available: Optional[bool] = None
        self._kysec_available: Optional[bool] = None
        self._platform = self._detect_platform()

    def _detect_platform(self) -> str:
        """检测当前平台."""
        try:
            with open("/etc/os-release") as f:
                content = f.read().lower()
            if "kylin" in content:
                return "kylin"
            if "uos" in content:
                return "uos"
        except Exception:
            pass
        if os.path.exists("/etc/redhat-release"):
            return "rhel"
        if os.path.exists("/etc/debian_version"):
            return "debian"
        return "linux"

    # ── SELinux ────────────────────────────────────────────────

    def check_selinux_enabled(self) -> bool:
        if self._selinux_available is not None:
            return self._selinux_available
        try:
            result = subprocess.run(
                ["getenforce"], capture_output=True, text=True, timeout=5
            )
            self._selinux_available = "enforc" in result.stdout.lower()
        except Exception:
            self._selinux_available = os.path.exists("/sys/fs/selinux")
        return self._selinux_available

    def _get_selinux_context(self, path: str = "") -> str:
        """获取文件或当前进程的 SELinux 上下文."""
        try:
            if path and os.path.exists(path):
                result = subprocess.run(
                    ["ls", "-Z", path], capture_output=True, text=True, timeout=5
                )
                parts = result.stdout.split()
                if parts:
                    return parts[0]
            else:
                result = subprocess.run(
                    ["id", "-Z"], capture_output=True, text=True, timeout=5
                )
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    # ── KYSEC (麒麟安全模块) ────────────────────────────────────

    def check_kylin_sec(self) -> bool:
        if self._kysec_available is not None:
            return self._kysec_available
        kysec_paths = [
            "/sys/kernel/security/kysec",
            "/proc/kysec",
            "/sys/kernel/security/kylin",
        ]
        self._kysec_available = any(os.path.exists(p) for p in kysec_paths)
        return self._kysec_available

    def _get_kysec_label(self) -> str:
        """读取 KYSEC 安全标签."""
        label_paths = [
            "/sys/kernel/security/kysec/current_label",
            "/proc/kysec/label",
        ]
        for p in label_paths:
            try:
                with open(p) as f:
                    return f.read().strip()
            except Exception:
                pass
        return ""

    # ── 主入口 ──────────────────────────────────────────────────

    def pre_exec_check(
        self, tool_name: str, arguments: Dict, risk_level: str
    ) -> MacCheckResult:
        """工具执行前的 MAC 检查.

        Args:
            tool_name: 工具名称 (如 file_inspector.read_file)
            arguments: 工具参数
            risk_level: 风险等级 (SAFE/READONLY/MODERATE/DANGEROUS)
        """
        reason_parts = []
        context = {}
        selinux_ctx = ""
        kysec_label = ""

        # 平台检测
        context["platform"] = self._platform

        # SELinux 检查
        if self.check_selinux_enabled():
            selinux_ctx = self._get_selinux_context()
            context["selinux_context"] = selinux_ctx
            reason_parts.append(f"SELinux enforcing, context={selinux_ctx}")

            # 对于涉及文件操作的工具，检查目标路径的上下文
            target_path = arguments.get("path", arguments.get("file_path", ""))
            if target_path and os.path.exists(target_path):
                target_ctx = self._get_selinux_context(target_path)
                context["target_selinux_context"] = target_ctx
                if selinux_ctx and target_ctx:
                    # 简化判断: 比较 type 部分 (第3字段)
                    proc_type = selinux_ctx.split(":")[2] if len(selinux_ctx.split(":")) >= 3 else ""
                    target_type = target_ctx.split(":")[2] if len(target_ctx.split(":")) >= 3 else ""
                    if proc_type and target_type and proc_type != target_type:
                        if self.enforce:
                            return MacCheckResult(
                                allowed=False,
                                context_before=selinux_ctx,
                                context_after=target_ctx,
                                reason=f"SELinux 上下文不匹配: 进程 {proc_type} 无法访问目标 {target_type}",
                                enforcing=True,
                                platform=self._platform,
                                details=context,
                            )
                        reason_parts.append(f"上下文不匹配(仅告警): {proc_type} vs {target_type}")

        # KYSEC 检查
        if self.check_kylin_sec():
            kysec_label = self._get_kysec_label()
            context["kysec_label"] = kysec_label
            if kysec_label:
                reason_parts.append(f"KYSEC label={kysec_label}")
                # 高风险操作在 KYSEC 下需要额外审查
                if risk_level in ("DANGEROUS", "MODERATE") and self.enforce:
                    context["kysec_restricted"] = True
                    reason_parts.append("高风险操作+KYSEC 管控环境，需人工审批")

        # 非麒麟环境降级
        if not self._selinux_available and not self._kysec_available:
            return MacCheckResult(
                allowed=True,
                reason=f"MAC 不可用 (平台: {self._platform})，放行",
                platform=self._platform,
                details=context,
            )

        reason = "; ".join(reason_parts) if reason_parts else "MAC 检查通过"
        return MacCheckResult(
            allowed=True,
            context_before=selinux_ctx,
            kysec_label=kysec_label,
            reason=reason,
            enforcing=self.enforce,
            platform=self._platform,
            details=context,
        )


_mac_checker: Optional[KylinMACChecker] = None


def get_mac_checker(enforce: bool = True) -> KylinMACChecker:
    global _mac_checker
    if _mac_checker is None:
        _mac_checker = KylinMACChecker(enforce=enforce)
    return _mac_checker

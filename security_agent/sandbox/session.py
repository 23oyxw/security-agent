"""SandboxSession — 用户视角的沙箱会话.

一次会话 = 用户的一次操作:
    1. preview() → 展示影响范围和风险
    2. execute() → 在隔离环境中执行
    3. changes() → 展示文件变更清单
    4. commit() 或 rollback() → 确认或回滚

设计原则:
    - 用户只需要知道这 5 个方法
    - 内部自动选择隔离策略（SandboxProfile.choose）
    - 所有返回结构都是人类可读的（summary 字段）
    - 完整 trace_id 贯穿
"""

from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from security_agent.sandbox.profile import SandboxProfile
from security_agent.sandbox.overlay import OverlayFS, ChangeReport
from security_agent.sandbox.namespace import NamespaceGuard
from security_agent.timeutil import now_iso


@dataclass
class PreviewCard:
    """预分析结果 — 用户决定「要不要执行」的依据."""
    command: str
    risk_level: str
    profile_name: str
    isolation_description: str       # "写时复制(OverlayFS) + 资源限制(CPU=30s/MEM=512MB)"
    layer_count: int
    affected_directory: str          # 受保护的工作目录
    estimated_impact: str            # "将影响 /var/log 下约 800 个文件"
    can_rollback: bool
    reason: str                      # 为什么选这个隔离级别
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command[:200],
            "risk_level": self.risk_level,
            "profile": self.profile_name,
            "isolation": self.isolation_description,
            "layer_count": self.layer_count,
            "affected_directory": self.affected_directory,
            "estimated_impact": self.estimated_impact,
            "can_rollback": self.can_rollback,
            "reason": self.reason,
            "trace_id": self.trace_id,
        }


@dataclass
class ExecutionCard:
    """执行结果 — 用户看到的「执行怎么样了」."""
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    elapsed_sec: float
    isolation_applied: str           # 实际应用的隔离措施
    trace_id: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:4000],
            "stderr": self.stderr[:2000],
            "elapsed_sec": self.elapsed_sec,
            "isolation": self.isolation_applied,
            "error": self.error,
            "trace_id": self.trace_id,
        }


class SandboxSession:
    """一次沙箱会话.

    用法:
        session = SandboxSession(work_dir="/var/log")
        preview = session.preview("find . -name '*.log' -mtime +30 -delete")
        # 用户看 preview → 决定
        result = session.execute("find . -name '*.log' -mtime +30 -delete", confirmed=True)
        changes = session.changes()
        # 用户看 changes → 决定
        session.commit()  # 或 session.rollback()
    """

    def __init__(
        self,
        work_dir: Path | str | None = None,
        *,
        risk_level: str | None = None,
        force_sandbox: bool = False,
    ):
        self._trace_id = uuid.uuid4().hex[:16]
        self._work_dir = Path(work_dir) if work_dir else Path(os.getcwd())
        self._risk_level = risk_level or "READONLY"
        self._force_sandbox = force_sandbox

        # 懒加载组件
        self._profile: SandboxProfile | None = None
        self._overlay: OverlayFS | None = None
        self._namespace: NamespaceGuard | None = None

        # 执行状态
        self._preview: PreviewCard | None = None
        self._result: ExecutionCard | None = None
        self._changes: ChangeReport | None = None

    # ---- 公开接口（5 个方法） ----

    def preview(self, command: str) -> PreviewCard:
        """预分析 — 执行前展示影响范围和防护措施.

        这是用户看到的「第一屏」：系统在说「我准备这样保护你的操作」。
        """
        # 1. 选择隔离 Profile
        self._profile = SandboxProfile.choose(self._risk_level)

        # 2. 估算影响范围
        estimated_impact = self._estimate_impact(command)

        # 3. 构造预览卡片
        self._preview = PreviewCard(
            command=command,
            risk_level=self._risk_level,
            profile_name=self._profile.name,
            isolation_description=self._profile.description,
            layer_count=self._profile.layer_count,
            affected_directory=str(self._work_dir),
            estimated_impact=estimated_impact,
            can_rollback=self._profile.overlay_enabled,
            reason=self._profile.reason,
            trace_id=self._trace_id,
        )
        return self._preview

    def execute(self, command: str, *, confirmed: bool = False) -> ExecutionCard:
        """在沙箱中执行命令.

        Args:
            command: shell 命令
            confirmed: 用户是否已确认（高风险操作需 true）

        Returns:
            ExecutionCard — 包含 stdout/stderr 和实际隔离措施
        """
        if self._profile is None:
            self.preview(command)

        if self._risk_level == "CRITICAL" and not confirmed:
            return ExecutionCard(
                ok=False, exit_code=-1, stdout="", stderr="",
                elapsed_sec=0, isolation_applied="拒绝执行",
                error="CRITICAL 等级操作需人工审批",
                trace_id=self._trace_id,
            )

        import time
        t0 = time.time()

        try:
            # 1. 设置 OverlayFS（如果需要）
            actual_work_dir = str(self._work_dir)
            if self._profile.overlay_enabled and self._profile.risk_level != "READONLY":
                self._overlay = OverlayFS()
                self._overlay.setup(self._work_dir)
                actual_work_dir = str(self._overlay.target_dir)

            # 2. 设置 namespace 隔离（如果需要）
            if self._profile.mount_ns_enabled:
                self._namespace = NamespaceGuard()
                self._namespace.apply_mount_ns()

            # 3. 执行命令
            proc = subprocess.run(
                command,
                shell=True,
                cwd=actual_work_dir,
                capture_output=True,
                text=True,
                timeout=self._profile.timeout_sec,
                env={**os.environ, "LANG": "C.UTF-8"},
            )

            elapsed = time.time() - t0
            self._result = ExecutionCard(
                ok=proc.returncode == 0,
                exit_code=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                elapsed_sec=round(elapsed, 2),
                isolation_applied=self._profile.description,
                trace_id=self._trace_id,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            self._result = ExecutionCard(
                ok=False, exit_code=-1, stdout="", stderr="",
                elapsed_sec=round(elapsed, 2),
                isolation_applied=self._profile.description,
                error=f"命令超时 ({self._profile.timeout_sec}s)",
                trace_id=self._trace_id,
            )
        except Exception as e:
            elapsed = time.time() - t0
            self._result = ExecutionCard(
                ok=False, exit_code=-1, stdout="", stderr=str(e),
                elapsed_sec=round(elapsed, 2),
                isolation_applied=self._profile.description,
                error=str(e),
                trace_id=self._trace_id,
            )

        return self._result

    def changes(self) -> ChangeReport:
        """执行后的文件变更清单 — 用户决定「要不要回滚」的依据.

        Returns:
            ChangeReport — 包含新增/修改/删除文件列表 + diff 摘要
        """
        if self._changes is not None:
            return self._changes

        if self._overlay is not None:
            self._changes = self._overlay.diff()
        else:
            self._changes = ChangeReport(
                sandbox_id=self._trace_id,
                can_rollback=False,
            )
        return self._changes

    def commit(self) -> dict[str, Any]:
        """确认变更，写时复制层合并到真实文件系统."""
        if self._overlay:
            self._overlay.commit()

        if self._namespace:
            self._namespace.cleanup()

        return {
            "action": "commit",
            "trace_id": self._trace_id,
            "committed_at": now_iso(),
        }

    def rollback(self) -> dict[str, Any]:
        """回滚 — 丢弃所有变更."""
        if self._overlay:
            self._overlay.rollback()

        if self._namespace:
            self._namespace.cleanup()

        return {
            "action": "rollback",
            "trace_id": self._trace_id,
            "rolled_back_at": now_iso(),
            "note": "OverlayFS 回滚：丢弃上层变更，原始文件不受影响。零拷贝，秒级完成。",
        }

    # ---- 上下文管理器 ----

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and self._overlay:
            self._overlay.rollback()
        if self._overlay:
            self._overlay.teardown()
        if self._namespace:
            self._namespace.cleanup()
        return False

    # ---- 内部 ----

    def _estimate_impact(self, command: str) -> str:
        """估算命令的影响范围."""
        if not self._work_dir.exists():
            return f"工作目录 {self._work_dir} 不存在"

        # 从命令中提取可能的路径参数
        import re
        paths_in_cmd = re.findall(r'(/[^\s;|&]+)', command)
        if paths_in_cmd:
            return f"指定路径: {', '.join(paths_in_cmd[:3])}"

        # 默认：影响工作目录
        try:
            file_count = sum(1 for _ in self._work_dir.rglob("*"))
            if file_count > 0:
                return f"将影响 {self._work_dir} 下约 {file_count} 个文件"
        except OSError:
            pass

        return f"将影响工作目录 {self._work_dir}"

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def status(self) -> dict[str, Any]:
        return {
            "trace_id": self._trace_id,
            "work_dir": str(self._work_dir),
            "risk_level": self._risk_level,
            "profile": self._profile.to_dict() if self._profile else None,
            "preview": self._preview.to_dict() if self._preview else None,
            "execution": self._result.to_dict() if self._result else None,
            "changes": self._changes.to_dict() if self._changes else None,
            "overlay_status": self._overlay.status() if self._overlay else None,
            "namespace_status": self._namespace.status() if self._namespace else None,
        }

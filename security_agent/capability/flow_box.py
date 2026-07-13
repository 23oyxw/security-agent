"""FlowBox — 所有工作流的装箱接口.

设计原则（装箱 + 美化）:
    工作流不散落在 skills/flows/、workflow/、skills/*/flows/。
    全部通过 FlowBox 暴露，调用方只需知道 flow 名字。

用法:
    box = FlowBox()
    result = box.run("secure_exec", command="rm /tmp/cache", user_confirmed=True)
    flows = box.list_all()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from security_agent.capability.guard import CapabilityGuard, GuardResult


@dataclass
class FlowResult:
    """一次工作流执行结果."""
    ok: bool
    flow_name: str
    steps_completed: int = 0
    steps_total: int = 0
    data: Any = None
    error: str = ""
    elapsed_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "flow": self.flow_name,
            "steps": f"{self.steps_completed}/{self.steps_total}",
            "error": self.error[:200],
            "elapsed_sec": self.elapsed_sec,
        }


class FlowBox:
    """工作流箱 — 所有 L2 Flow 的统一调用入口.

    已注册的 Flow:
        secure_exec      — 三层防御评估 → 安全执行
        alert_response   — 告警 → Skill 路由 → 汇总
        scan_report      — 安全扫描 → 格式化报告
        system_cleanup   — 扫描可清理项 → 安全执行
        cpu_stress       — 多核压测 → 阈值自动停止
    """

    def __init__(self):
        self._guard = CapabilityGuard()
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            from security_agent.skills.flows.runner import list_flows
            self._loaded = True
        except ImportError:
            pass

    def run(
        self,
        flow_name: str,
        *,
        command: str = "",
        user_confirmed: bool = False,
        timeout: float = 60.0,
        **params: Any,
    ) -> FlowResult:
        """运行一个工作流.

        Args:
            flow_name: 工作流名（secure_exec / alert_response / scan_report / system_cleanup / cpu_stress）
            command: 要执行的命令（secure_exec 需要）
            user_confirmed: 用户是否已确认
            timeout: 超时
            **params: 工作流特定参数

        Returns:
            FlowResult
        """
        self._ensure_loaded()

        def _call():
            from security_agent.skills.flows.runner import run_skill_flow
            import asyncio
            return asyncio.run(run_skill_flow(
                flow_name,
                command=command,
                user_confirmed=user_confirmed,
                **params,
            ))

        key = f"flow:{flow_name}"
        guarded: GuardResult = self._guard.call(key, _call, timeout=timeout)
        return FlowResult(
            ok=guarded.ok,
            flow_name=flow_name,
            data=guarded.data,
            error=guarded.error,
            elapsed_sec=guarded.elapsed_sec,
        )

    def list_all(self) -> list[dict[str, str]]:
        """列出所有可用工作流."""
        self._ensure_loaded()
        try:
            from security_agent.skills.flows.runner import list_flows
            flows = list_flows()
            return [
                {
                    "name": f,
                    "description": f"L2 Flow: {f}",
                }
                for f in (flows or [])
            ]
        except ImportError:
            return [
                {"name": "secure_exec", "description": "三层防御 → 安全执行"},
                {"name": "alert_response", "description": "告警 → Skill 路由"},
                {"name": "scan_report", "description": "扫描 → 报告"},
                {"name": "system_cleanup", "description": "清理 → 安全执行"},
                {"name": "cpu_stress", "description": "压测 → 自动停止"},
            ]

    def guard_status(self) -> dict[str, Any]:
        return self._guard.status()

"""CapabilityRegistry — 统一能力注册中心（装箱模式）.

主线（agent/brain.py, agent/orchestrator.py）**只 import 这一个**，
不再需要分别知道 tools/、mcp/、skills/、workflow/、skills/flows/ 的细节。

用法:
    from security_agent.capability import CapabilityRegistry

    caps = CapabilityRegistry()

    # 工具调用（自动熔断+超时保护）
    result = caps.tools.invoke("get_system_health", {"detail": True})

    # 工作流执行（自动熔断+超时保护）
    result = caps.flows.run("secure_exec", command="...", user_confirmed=True)

    # MCP 热插拔
    caps.plugins.reload()

    # 查看所有熔断器状态
    caps.status()
"""

from __future__ import annotations

from typing import Any

from security_agent.capability.tool_box import ToolBox, ToolResult
from security_agent.capability.flow_box import FlowBox, FlowResult
from security_agent.capability.plugin_box import PluginBox
from security_agent.capability.guard import CapabilityGuard


class CapabilityRegistry:
    """统一能力注册中心 — 主线的唯一能力入口.

    装箱结构:
        .tools    → ToolBox    — 所有工具（自动熔断保护）
        .flows    → FlowBox    — 所有工作流（自动熔断保护）
        .plugins  → PluginBox  — MCP 热插拔管理
    """

    def __init__(self):
        self.tools = ToolBox()
        self.flows = FlowBox()
        self.plugins = PluginBox()

    def status(self) -> dict[str, Any]:
        """总览：所有箱子的健康状态."""
        return {
            "tools": {
                "count": len(self.tools.list_all()),
                "guard": self.tools.guard_status(),
            },
            "flows": {
                "available": [f["name"] for f in self.flows.list_all()],
                "guard": self.flows.guard_status(),
            },
            "plugins": self.plugins.status(),
        }

    # ---- 便捷方法 ----

    def invoke_tool(self, name: str, **params: Any) -> ToolResult:
        """快捷工具调用."""
        return self.tools.invoke(name, params)

    def run_flow(self, name: str, **params: Any) -> FlowResult:
        """快捷工作流执行."""
        return self.flows.run(name, **params)

    def hot_reload(self) -> dict[str, Any]:
        """快捷热插拔."""
        return self.plugins.reload()

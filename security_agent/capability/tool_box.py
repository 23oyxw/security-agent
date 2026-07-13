"""ToolBox — 所有工具的装箱接口.

设计原则（装箱）:
    主线只需调 ToolBox.invoke(name, params)，
    不需要知道 tool 来自 skills/ 还是 mcp/ 还是 tools/。

用法:
    box = ToolBox()
    result = box.invoke("get_system_health", {"detail": True})
    tools = box.list_all()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from security_agent.capability.guard import CapabilityGuard, GuardResult


@dataclass
class ToolResult:
    """一次工具调用结果."""
    ok: bool
    tool_name: str
    data: Any = None
    error: str = ""
    elapsed_sec: float = 0.0
    guarded: bool = True   # 是否经过 CapabilityGuard 保护

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool_name,
            "error": self.error[:200],
            "elapsed_sec": self.elapsed_sec,
            "guarded": self.guarded,
        }


class ToolBox:
    """工具箱 — 所有工具的统一调用入口.

    工具来源（自动聚合）:
        1. tools/registry — 核心工具注册表
        2. skills/ — Skill 插件提供的工具
        3. mcp/ — MCP 协议工具（stdio/http）

    调用自动经过 CapabilityGuard 保护。
    """

    def __init__(self):
        self._guard = CapabilityGuard()
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            from security_agent.tools.registry import list_tools
            self._loaded = True
        except ImportError:
            pass

    def invoke(self, name: str, params: dict[str, Any] | None = None, *, timeout: float = 30.0) -> ToolResult:
        """调用一个工具（自动记录统计）.

        Args:
            name: 工具名（如 "get_system_health"）
            params: 工具参数
            timeout: 超时秒数

        Returns:
            ToolResult
        """
        self._ensure_loaded()
        params = params or {}
        import time
        t0 = time.time()

        def _call():
            from security_agent.tools.registry import call_tool
            return call_tool(name, **params)

        key = f"tool:{name}"
        guarded: GuardResult = self._guard.call(key, _call, timeout=timeout)

        # 自动记录统计（MCP 评分维度硬性要求）
        elapsed_ms = (time.time() - t0) * 1000
        from security_agent.capability.tool_stats import record_tool_call
        record_tool_call(name, ok=guarded.ok, elapsed_ms=elapsed_ms, error=guarded.error)

        return ToolResult(
            ok=guarded.ok,
            tool_name=name,
            data=guarded.data,
            error=guarded.error,
            elapsed_sec=guarded.elapsed_sec,
            guarded=True,
        )

    def invoke_raw(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """直接调用工具，不经过 guard（用于内部已有保护的场景）."""
        self._ensure_loaded()
        try:
            from security_agent.tools.registry import call_tool
            return call_tool(name, **(params or {}))
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有可用工具."""
        self._ensure_loaded()
        try:
            from security_agent.tools.registry import list_tools
            tools = list_tools()
            return [
                {
                    "name": t.get("name", ""),
                    "description": t.get("description", "")[:200],
                    "parameters": t.get("parameters", {}),
                }
                for t in (tools or [])
            ]
        except ImportError:
            return []

    def list_by_cluster(self) -> dict[str, list[str]]:
        """按四大工具簇分组."""
        self._ensure_loaded()
        try:
            from security_agent.tools.cluster_map import TOOL_CLUSTERS
            return dict(TOOL_CLUSTERS)
        except ImportError:
            return {"metrics": [], "logs": [], "repair": [], "dispatch": []}

    def guard_status(self) -> dict[str, Any]:
        """查看工具调用的熔断器状态."""
        return self._guard.status()

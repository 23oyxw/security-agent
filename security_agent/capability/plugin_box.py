"""PluginBox — MCP 热插拔管理.

设计原则（装箱）:
    热插拔不是散落在 api/mcp_host.py + mcp/registry.py + skills/registry.py，
    而是统一通过 PluginBox 管理。

用法:
    box = PluginBox()
    box.reload()            # 热插拔：重新发现+注册所有 Skill
    box.list_servers()      # 列出 MCP 服务
    box.register("my_skill", command="python my_skill.py")
"""

from __future__ import annotations

from typing import Any


class PluginBox:
    """插件箱 — MCP 热插拔统一管理."""

    def reload(self) -> dict[str, Any]:
        """热插拔：重新发现 Skill、合并工具、刷新 MCP Host."""
        try:
            from security_agent.mcp.registry import McpPluginRegistry
            registry = McpPluginRegistry()
            return registry.reload()
        except ImportError as e:
            return {"ok": False, "error": str(e)}

    def list_servers(self) -> list[dict[str, Any]]:
        """列出所有已注册的 MCP 服务."""
        try:
            from security_agent.api.mcp_host import get_mcp_host
            host = get_mcp_host()
            return host.list_servers()
        except ImportError:
            return []

    def list_tools(self) -> list[dict[str, Any]]:
        """列出所有 MCP 工具."""
        try:
            from security_agent.api.mcp_host import get_mcp_host
            host = get_mcp_host()
            return host.get_all_tools()
        except ImportError:
            return []

    def register(
        self,
        name: str,
        *,
        command: str = "",
        protocol: str = "stdio",
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """注册一个新的 MCP 插件."""
        try:
            from security_agent.mcp.registry import McpPluginRegistry
            registry = McpPluginRegistry()
            return registry.register_server(
                name, command=command, protocol=protocol, tools=tools,
            )
        except ImportError as e:
            return {"ok": False, "error": str(e)}

    def unregister(self, name: str) -> dict[str, Any]:
        """移除一个 MCP 插件."""
        try:
            from security_agent.mcp.registry import McpPluginRegistry
            _ = McpPluginRegistry()
            # McpPluginRegistry 目前无 unregister，通过 API 层实现
            from security_agent.api.mcp_host import get_mcp_host
            host = get_mcp_host()
            host.remove_server(name)
            return {"ok": True, "name": name}
        except ImportError as e:
            return {"ok": False, "error": str(e)}

    def status(self) -> dict[str, Any]:
        """插件系统状态."""
        try:
            servers = self.list_servers()
            tools = self.list_tools()
        except Exception:
            servers, tools = [], []
        return {
            "servers_count": len(servers),
            "tools_count": len(tools),
            "servers": [s.get("name", "?") for s in servers],
        }

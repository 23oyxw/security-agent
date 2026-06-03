"""MCP 热插拔注册中心 — 同步 Skill 与 manifest，刷新 Host 与工具注册表."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from security_agent import config

logger = logging.getLogger(__name__)


class McpPluginRegistry:
    """运行时 MCP 服务注册（择优自 qt01 思路，轻量实现）."""

    def __init__(self) -> None:
        self._manifest_path = config.DATA_DIR / "mcp" / "manifest.json"
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def reload(self) -> Dict[str, Any]:
        """重新发现 Skill、合并工具、刷新 McpHost."""
        from security_agent.skills.registry import auto_discover, merge_skill_tools_into_registry
        from security_agent.api.mcp_host import get_mcp_host

        auto_discover()
        merge_skill_tools_into_registry()
        host = get_mcp_host()
        host.reload_from_registry()
        servers = host.list_servers()
        return {
            "ok": True,
            "servers_count": len(servers),
            "tools_count": len(host.get_all_tools()),
            "servers": [s["name"] for s in servers],
        }

    def register_server(
        self,
        name: str,
        *,
        command: str = "",
        protocol: str = "stdio",
        tools: Optional[List[Dict[str, Any]]] = None,
        status: str = "running",
    ) -> Dict[str, Any]:
        """注册或更新一个 MCP 服务条目并持久化 manifest."""
        from security_agent.api.mcp_host import get_mcp_host

        host = get_mcp_host()
        host.register_server(name, command=command, protocol=protocol, tools=tools or [], status=status)
        self._persist_manifest(host.list_servers())
        return host.get_server(name) or {"name": name, "status": status}

    def unregister_server(self, name: str) -> bool:
        from security_agent.api.mcp_host import get_mcp_host

        host = get_mcp_host()
        ok = host.unregister_server(name)
        if ok:
            self._persist_manifest(host.list_servers())
        return ok

    def list_manifest(self) -> List[Dict[str, Any]]:
        if not self._manifest_path.exists():
            return []
        try:
            data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            return list(data.get("servers", []))
        except Exception:
            return []

    def _persist_manifest(self, servers: List[Dict[str, Any]]) -> None:
        payload = {
            "version": 1,
            "servers": [
                {
                    "name": s["name"],
                    "command": s.get("command", ""),
                    "protocol": s.get("protocol", "stdio"),
                    "tools": s.get("tools", []),
                }
                for s in servers
            ],
        }
        self._manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


_registry: Optional[McpPluginRegistry] = None


def get_mcp_registry() -> McpPluginRegistry:
    global _registry
    if _registry is None:
        _registry = McpPluginRegistry()
    return _registry


def reload_mcp_plugins() -> Dict[str, Any]:
    return get_mcp_registry().reload()

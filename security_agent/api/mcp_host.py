"""MCP Host 集中管理器 — 包装 mcp/ 模块"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from security_agent import config


@dataclass
class McpServerStatus:
    """MCP 服务器状态"""
    name: str
    status: str = "stopped"  # running / stopped / error
    tools_count: int = 0
    tools: List[Dict[str, Any]] = field(default_factory=list)
    protocol: str = "stdio"
    command: str = ""
    last_health_check: Optional[float] = None
    error_message: str = ""


class McpHostManager:
    """MCP 服务集中管理器"""

    def __init__(self):
        self._servers: Dict[str, McpServerStatus] = {}
        self._manifest_path = config.DATA_DIR / "mcp" / "manifest.json"
        self._load_manifest()

    def _load_manifest(self) -> None:
        """从 manifest.json 加载服务配置"""
        if self._manifest_path.exists():
            try:
                data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
                for srv in data.get("servers", []):
                    name = srv.get("name", "unknown")
                    self._servers[name] = McpServerStatus(
                        name=name,
                        command=srv.get("command", ""),
                        protocol=srv.get("protocol", "stdio"),
                        tools_count=len(srv.get("tools", [])),
                        tools=srv.get("tools", []),
                        status="stopped",
                    )
            except Exception:
                pass
        if not self._servers:
            self._load_from_skills()

    def reload_from_registry(self) -> None:
        """热插拔：清空后从 Skill 重建，再合并 manifest 中的自定义服务."""
        self._servers.clear()
        self._load_from_skills()
        if self._manifest_path.exists():
            try:
                data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
                for srv in data.get("servers", []):
                    name = srv.get("name", "")
                    if not name or name in self._servers:
                        continue
                    self.register_server(
                        name,
                        command=srv.get("command", ""),
                        protocol=srv.get("protocol", "stdio"),
                        tools=srv.get("tools", []),
                        status="stopped",
                    )
            except Exception:
                pass

    def register_server(
        self,
        name: str,
        *,
        command: str = "",
        protocol: str = "stdio",
        tools: List[Dict[str, Any]] | None = None,
        status: str = "running",
    ) -> None:
        tool_list = tools or []
        self._servers[name] = McpServerStatus(
            name=name,
            command=command,
            protocol=protocol,
            tools_count=len(tool_list),
            tools=tool_list,
            status=status,
        )

    def unregister_server(self, name: str) -> bool:
        if name in self._servers:
            del self._servers[name]
            return True
        return False

    def _load_from_skills(self) -> None:
        """manifest 缺失时从 Skill 注册中心填充 MCP 服务列表"""
        try:
            from security_agent.skills.registry import _skills, auto_discover

            auto_discover()
            for name, skill in _skills.items():
                tools = [
                    {"name": t.name, "description": t.description}
                    for t in skill.get_tools()
                ]
                self._servers[name] = McpServerStatus(
                    name=name,
                    command=f"security_agent.skills.{name}",
                    protocol="stdio",
                    tools_count=len(tools),
                    tools=tools,
                    status="running",
                )
        except Exception:
            pass

    def list_servers(self) -> List[Dict[str, Any]]:
        """列出所有 MCP 服务器"""
        return [
            {
                "name": s.name,
                "status": s.status,
                "tools_count": s.tools_count,
                "tools": s.tools,
                "protocol": s.protocol,
                "command": s.command,
                "last_health_check": s.last_health_check,
                "error_message": s.error_message,
            }
            for s in self._servers.values()
        ]

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """获取单个服务器状态"""
        srv = self._servers.get(name)
        if not srv:
            return None
        return {
            "name": srv.name,
            "status": srv.status,
            "tools_count": srv.tools_count,
            "tools": srv.tools,
            "protocol": srv.protocol,
            "command": srv.command,
            "last_health_check": srv.last_health_check,
            "error_message": srv.error_message,
        }

    def health_check(self, name: str) -> Dict[str, Any]:
        """健康检查（轻量级）"""
        srv = self._servers.get(name)
        if not srv:
            return {"status": "not_found", "name": name}
        srv.last_health_check = time.time()
        # 简单检查：更新时间戳
        return {
            "status": srv.status,
            "name": name,
            "timestamp": srv.last_health_check,
        }

    def health_check_all(self) -> List[Dict[str, Any]]:
        """全部健康检查"""
        results = []
        for name in self._servers:
            results.append(self.health_check(name))
        return results

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有服务器的工具列表"""
        tools = []
        for srv in self._servers.values():
            for tool in srv.tools:
                tools.append({
                    **tool,
                    "server_name": srv.name,
                })
        return tools


# 全局单例
_mcp_host: Optional[McpHostManager] = None


def get_mcp_host() -> McpHostManager:
    global _mcp_host
    if _mcp_host is None:
        _mcp_host = McpHostManager()
    return _mcp_host
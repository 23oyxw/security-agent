"""MCP Client Manager — 统一管理多个 MCP 服务的客户端.

支持两种模式：
1. stdio: 本地进程通信（适合嵌入式）
2. http: HTTP/SSE 远程调用（适合分布式部署）

示例：
    >>> from security_agent.skills.mcp_client import MCPClientManager
    >>> 
    >>> # HTTP 模式连接多个服务
    >>> manager = MCPClientManager()
    >>> await manager.connect_http("healthcheck", "127.0.0.1", 8081)
    >>> await manager.connect_http("log_analyzer", "127.0.0.1", 8082)
    >>> 
    >>> # 调用工具
    >>> result = await manager.call_tool("healthcheck", "health_full_check", {})
    >>> 
    >>> # 关闭所有连接
    >>> await manager.close_all()
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urljoin

# 可选依赖：aiohttp，如果没有则使用标准库
AIOHTTP_AVAILABLE = False
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    pass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from security_agent import config

logger = logging.getLogger(__name__)


@dataclass
class MCPToolInfo:
    """MCP 工具信息."""
    name: str
    description: str
    parameters: dict[str, Any]
    requires_confirmation: bool = False
    # 读写属性标记
    is_read_only: bool = True  # 默认只读
    cost_estimate: float = 0.0  # 预估成本（单位：分）


@dataclass
class MCPServiceInfo:
    """MCP 服务信息."""
    name: str
    display_name: str
    description: str
    version: str
    tools: list[MCPToolInfo] = field(default_factory=list)
    # 运行时信息
    mode: str = "stdio"  # "stdio" | "http"
    host: str = ""
    port: int = 0
    connected: bool = False
    last_error: str = ""


@dataclass
class MCPCallRecord:
    """MCP 调用记录（用于成本追踪）."""
    timestamp: str
    service: str
    tool: str
    duration_ms: float
    success: bool
    cost_estimate: float  # 预估成本（分）
    error: str = ""


class MCPHttpClient:
    """HTTP 模式 MCP 客户端（简化实现）."""
    
    def __init__(self, host: str, port: int, service_name: str = ""):
        self.host = host
        self.port = port
        self.service_name = service_name
        self.base_url = f"http://{host}:{port}"
        self._session: Any | None = None  # aiohttp.ClientSession or None
        self._info: MCPServiceInfo | None = None
    
    def _is_read_only_tool(self, tool_name: str) -> bool:
        """判断工具是否为只读（根据命名约定）.

        注意：这是启发式判断，精确判断应使用工具的 requires_confirmation 属性。
        """
        # 写入类关键词（精确匹配，避免误伤）
        write_patterns = [
            "_write", "_modify", "_update", "_delete", "_remove",
            "_edit", "_change_", "_set_", "_add_", "_create_", "_exec",
            "_heal", "_fix", "_repair", "_kill", "restart_", "_stop",
            "self_heal", "auto_fix", "clear_", "clean_", "purge_",
        ]
        name_lower = tool_name.lower()
        # 特殊例外：health 不是 heal
        if name_lower.startswith("health"):
            return True
        return not any(pat in name_lower for pat in write_patterns)
    
    def _estimate_tool_cost(self, tool_name: str) -> float:
        """预估工具调用成本（基于复杂度）."""
        # 简单启发式：扫描类工具成本较高
        if "scan" in tool_name.lower() or "full" in tool_name.lower():
            return 0.5  # 0.5 分
        elif "analysis" in tool_name.lower() or "analyze" in tool_name.lower():
            return 0.3
        else:
            return 0.1  # 默认 0.1 分
    
    async def connect(self) -> MCPServiceInfo:
        """连接服务并获取信息."""
        # 使用标准库实现
        import urllib.request
        import urllib.error
        
        try:
            # 获取服务信息
            req = urllib.request.Request(
                f"{self.base_url}/info",
                method="GET",
                headers={"Accept": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                info_data = data.get("info", data)
                
                self._info = MCPServiceInfo(
                    name=info_data.get("name", self.service_name),
                    display_name=info_data.get("display_name", self.service_name),
                    description=info_data.get("description", ""),
                    version=info_data.get("version", "1.0.0"),
                    mode="http",
                    host=self.host,
                    port=self.port,
                    connected=True,
                    tools=[
                        MCPToolInfo(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                            parameters=t.get("parameters", {}),
                            requires_confirmation=t.get("requires_confirmation", False),
                            is_read_only=self._is_read_only_tool(t.get("name", "")),
                            cost_estimate=self._estimate_tool_cost(t.get("name", "")),
                        )
                        for t in info_data.get("tools", [])
                    ]
                )
                return self._info
                
        except urllib.error.HTTPError as e:
            logger.error(f"连接 MCP HTTP 服务失败 {self.base_url}: HTTP {e.code}")
            raise ConnectionError(f"HTTP {e.code}")
        except Exception as e:
            logger.error(f"连接 MCP HTTP 服务失败 {self.base_url}: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """调用工具（HTTP 模式使用 JSON-RPC）."""
        import urllib.request
        import urllib.error
        
        # 构造 JSON-RPC 请求
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            }
        }).encode("utf-8")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            req = urllib.request.Request(
                f"{self.base_url}/messages",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                duration = (asyncio.get_event_loop().time() - start_time) * 1000
                result = json.loads(resp.read().decode("utf-8"))
                
                return {
                    "success": True,
                    "result": result,
                    "duration_ms": duration,
                }
                
        except urllib.error.HTTPError as e:
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            return {
                "success": False,
                "error": f"HTTP {e.code}",
                "duration_ms": duration,
            }
        except Exception as e:
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            return {
                "success": False,
                "error": str(e),
                "duration_ms": duration,
            }
    
    async def close(self):
        """关闭连接（HTTP 模式无状态，无需关闭）."""
        self._session = None
        self._info = None


class MCPClientManager:
    """MCP 客户端管理器 — 统一管理多个 MCP 服务连接."""
    
    def __init__(self):
        self._http_clients: dict[str, MCPHttpClient] = {}
        self._services: dict[str, MCPServiceInfo] = {}
        self._call_history: list[MCPCallRecord] = []
        self._max_history = 1000
    
    # ---- 连接管理 ----
    
    async def connect_http(self, name: str, host: str, port: int) -> MCPServiceInfo:
        """连接 HTTP 模式的 MCP 服务."""
        client = MCPHttpClient(host, port, name)
        info = await client.connect()
        
        self._http_clients[name] = client
        self._services[name] = info
        
        logger.info(f"已连接 MCP 服务 {name} @ {host}:{port}, {len(info.tools)} 个工具")
        return info
    
    async def connect_stdio(self, name: str, module_path: str) -> MCPServiceInfo:
        """连接 stdio 模式的 MCP 服务（待实现）."""
        # TODO: 使用 mcp.client.stdio 实现
        raise NotImplementedError("stdio 模式通过 mcp/client.py 实现")
    
    async def disconnect(self, name: str) -> bool:
        """断开指定服务连接."""
        if name in self._http_clients:
            await self._http_clients[name].close()
            del self._http_clients[name]
        
        if name in self._services:
            del self._services[name]
        
        logger.info(f"已断开 MCP 服务 {name}")
        return True
    
    async def close_all(self):
        """关闭所有连接."""
        for name in list(self._http_clients.keys()):
            await self.disconnect(name)
    
    # ---- 服务发现 ----
    
    def list_services(self) -> list[MCPServiceInfo]:
        """列出所有已连接的服务."""
        return list(self._services.values())
    
    def get_service(self, name: str) -> MCPServiceInfo | None:
        """获取指定服务信息."""
        return self._services.get(name)
    
    def get_tool_info(self, service: str, tool: str) -> MCPToolInfo | None:
        """获取工具信息."""
        svc = self._services.get(service)
        if not svc:
            return None
        for t in svc.tools:
            if t.name == tool:
                return t
        return None
    
    # ---- 工具调用 ----
    
    async def call_tool(
        self,
        service: str,
        tool: str,
        arguments: dict[str, Any],
        track_cost: bool = True,
    ) -> dict[str, Any]:
        """调用指定服务的工具."""
        from security_agent.timeutil import now_iso
        
        client = self._http_clients.get(service)
        if not client:
            return {
                "success": False,
                "error": f"服务 {service} 未连接",
            }
        
        # 获取工具信息用于成本计算
        tool_info = self.get_tool_info(service, tool)
        cost_estimate = tool_info.cost_estimate if tool_info else 0.1
        
        # 执行调用
        result = await client.call_tool(tool, arguments)
        
        # 记录调用
        if track_cost:
            record = MCPCallRecord(
                timestamp=now_iso(),
                service=service,
                tool=tool,
                duration_ms=result.get("duration_ms", 0),
                success=result.get("success", False),
                cost_estimate=cost_estimate,
                error=result.get("error", ""),
            )
            self._call_history.append(record)
            
            # 限制历史记录大小
            if len(self._call_history) > self._max_history:
                self._call_history = self._call_history[-self._max_history:]
        
        return result
    
    async def call_tool_with_confirm(
        self,
        service: str,
        tool: str,
        arguments: dict[str, Any],
        confirm_callback: Callable[[str, str, dict], bool] | None = None,
    ) -> dict[str, Any]:
        """调用工具，需要时进行确认.
        
        Args:
            confirm_callback: 确认回调函数 (service, tool, args) -> bool
        """
        tool_info = self.get_tool_info(service, tool)
        
        # 检查是否需要确认
        needs_confirm = False
        if tool_info:
            needs_confirm = tool_info.requires_confirmation or not tool_info.is_read_only
        
        if needs_confirm:
            if confirm_callback:
                if not confirm_callback(service, tool, arguments):
                    return {
                        "success": False,
                        "error": "用户取消操作",
                        "cancelled": True,
                    }
            else:
                # 默认拒绝高风险操作
                return {
                    "success": False,
                    "error": "高风险操作需要确认回调",
                    "needs_confirmation": True,
                }
        
        return await self.call_tool(service, tool, arguments)
    
    # ---- 成本追踪 ----
    
    def get_cost_summary(self) -> dict[str, Any]:
        """获取成本统计摘要."""
        if not self._call_history:
            return {
                "total_calls": 0,
                "total_cost": 0.0,
                "by_service": {},
                "by_tool": {},
            }
        
        total_cost = sum(r.cost_estimate for r in self._call_history)
        
        by_service: dict[str, dict] = {}
        by_tool: dict[str, dict] = {}
        
        for record in self._call_history:
            # 按服务统计
            if record.service not in by_service:
                by_service[record.service] = {"calls": 0, "cost": 0.0}
            by_service[record.service]["calls"] += 1
            by_service[record.service]["cost"] += record.cost_estimate
            
            # 按工具统计
            tool_key = f"{record.service}/{record.tool}"
            if tool_key not in by_tool:
                by_tool[tool_key] = {"calls": 0, "cost": 0.0}
            by_tool[tool_key]["calls"] += 1
            by_tool[tool_key]["cost"] += record.cost_estimate
        
        return {
            "total_calls": len(self._call_history),
            "total_cost": round(total_cost, 4),
            "avg_cost_per_call": round(total_cost / len(self._call_history), 4),
            "by_service": {k: {"calls": v["calls"], "cost": round(v["cost"], 4)} 
                          for k, v in by_service.items()},
            "by_tool": {k: {"calls": v["calls"], "cost": round(v["cost"], 4)} 
                       for k, v in by_tool.items()},
        }
    
    def get_recent_calls(self, limit: int = 50) -> list[dict]:
        """获取最近的调用记录."""
        return [
            {
                "timestamp": r.timestamp,
                "service": r.service,
                "tool": r.tool,
                "duration_ms": round(r.duration_ms, 2),
                "success": r.success,
                "cost": r.cost_estimate,
            }
            for r in self._call_history[-limit:]
        ]
    
    def clear_history(self):
        """清空调用历史."""
        self._call_history.clear()
    
    # ---- 只读检查 ----
    
    def check_read_only(self, service: str, tool: str) -> dict[str, Any]:
        """检查工具是否为只读操作."""
        tool_info = self.get_tool_info(service, tool)
        
        if not tool_info:
            return {
                "known": False,
                "read_only": False,
                "warning": "未知工具，默认视为高风险",
            }
        
        return {
            "known": True,
            "read_only": tool_info.is_read_only,
            "requires_confirmation": tool_info.requires_confirmation,
            "warning": None if tool_info.is_read_only else "此工具可能修改系统状态",
        }


# ---- 便捷函数 ----

async def quick_connect_all(
    services: dict[str, tuple[str, int]] | None = None
) -> MCPClientManager:
    """快速连接所有默认 MCP 服务.
    
    Args:
        services: {服务名: (host, port)} 字典，默认使用标准端口
    
    Returns:
        配置好的 MCPClientManager
    """
    if services is None:
        services = {
            "healthcheck": ("127.0.0.1", 8081),
            "log_analyzer": ("127.0.0.1", 8082),
            "config_manager": ("127.0.0.1", 8083),
            "security_hardening": ("127.0.0.1", 8084),
            "incident_responder": ("127.0.0.1", 8085),
        }
    
    manager = MCPClientManager()
    
    for name, (host, port) in services.items():
        try:
            await manager.connect_http(name, host, port)
        except Exception as e:
            logger.warning(f"连接 {name} 失败: {e}")
    
    return manager

"""MCP Skill Server 基类 — 每个 Skill 成为独立的 MCP 服务.

使用方式:
    1. 继承 MCPSkillServer，实现 get_tools()
    2. 运行: python -m security_agent.skills.xxx.mcp_server
    3. 或通过 launcher: python -m security_agent.skills.launcher healthcheck

支持传输模式:
    - stdio (默认): 适合本地 Agent 调用
    - http/sse: 适合远程部署

示例:
    >>> from security_agent.skills.mcp_base import MCPSkillServer
    >>> class HealthServer(MCPSkillServer):
    ...     name = "healthcheck"
    ...     display_name = "健康巡检"
    ...     def get_tools(self): ...
    >>> server = HealthServer()
    >>> server.run()  # 启动服务
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
from abc import ABC, abstractmethod
from typing import Any, Callable
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
import uvicorn


@dataclass
class MCPTool:
    """MCP 工具定义."""
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    requires_confirmation: bool = False


class MCPSkillServer(ABC):
    """Skill MCP Server 基类.
    
    每个 Skill 继承此类，实现 get_tools() 方法，即可成为独立的 MCP 服务。
    """
    
    # 子类必须定义
    name: str = ""  # skill 唯一标识
    display_name: str = ""  # 显示名称
    description: str = ""  # 描述
    version: str = "1.0.0"
    port: int = 0  # HTTP 模式端口（0=自动分配）
    
    def __init__(self):
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} 必须定义 name 属性")
        
        self._mcp = FastMCP(self.name)
        self._tools: dict[str, MCPTool] = {}
        self._register_tools()
    
    @abstractmethod
    def get_tools(self) -> list[MCPTool]:
        """返回本 Skill 提供的工具列表.
        
        子类必须实现此方法，返回工具定义列表。
        """
        ...
    
    def _register_tools(self) -> None:
        """注册所有工具到 FastMCP."""
        tools = self.get_tools()
        
        for tool in tools:
            self._tools[tool.name] = tool
            self._bind_tool(tool)
    
    def _bind_tool(self, tool: MCPTool) -> None:
        """将工具绑定到 FastMCP."""
        sig = inspect.signature(tool.handler)
        params = [
            p for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        ]
        
        # 生成 JSON Schema 参数定义
        schema = tool.parameters or {"type": "object", "properties": {}}
        
        @self._mcp.tool(
            name=tool.name,
            description=tool.description,
        )
        async def _wrapped(**kwargs: Any) -> str:
            """包装器：调用实际处理函数并返回字符串."""
            try:
                # 参数校验和转换
                validated = self._validate_params(tool, kwargs)
                
                # 调用处理函数
                result = tool.handler(**validated)
                
                # 支持异步处理函数
                if inspect.isawaitable(result):
                    result = await result
                
                # 统一返回字符串
                if isinstance(result, dict):
                    return json.dumps(result, ensure_ascii=False, indent=2)
                return str(result)
                
            except Exception as e:
                return json.dumps({
                    "error": str(e),
                    "tool": tool.name,
                    "status": "failed"
                }, ensure_ascii=False)
        
        # 应用 schema
        _wrapped.__doc__ = tool.description
    
    def _validate_params(self, tool: MCPTool, kwargs: dict) -> dict:
        """验证并转换参数."""
        schema = tool.parameters or {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # 检查必填参数
        for key in required:
            if key not in kwargs:
                raise ValueError(f"缺少必填参数: {key}")
        
        # 类型转换
        validated = {}
        for key, value in kwargs.items():
            if key in properties:
                prop = properties[key]
                ptype = prop.get("type", "string")
                
                try:
                    if ptype == "integer":
                        validated[key] = int(value)
                    elif ptype == "number":
                        validated[key] = float(value)
                    elif ptype == "boolean":
                        validated[key] = bool(value)
                    else:
                        validated[key] = str(value)
                except (ValueError, TypeError):
                    validated[key] = value
            else:
                validated[key] = value
        
        return validated
    
    def get_info(self) -> dict[str, Any]:
        """返回 Skill 信息."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                    "requires_confirmation": t.requires_confirmation,
                }
                for t in self._tools.values()
            ],
        }
    
    def run_stdio(self) -> None:
        """以 stdio 模式运行（默认，适合本地 Agent）."""
        self._mcp.run(transport="stdio")
    
    def run_http(self, host: str = "127.0.0.1", port: int | None = None) -> None:
        """以 HTTP/SSE 模式运行（适合远程部署）."""
        port = port or self.port or 0
        
        sse = SseServerTransport("/messages/")
        
        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self._mcp._mcp_server.run(
                    streams[0], streams[1], self._mcp._mcp_server.create_initialization_options()
                )
        
        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_sse),
            ],
        )
        
        # 添加 info 端点
        @starlette_app.route("/info")
        async def info(request):
            return {"info": self.get_info()}
        
        uvicorn.run(starlette_app, host=host, port=port, log_level="info")
    
    def run(self, transport: str = "stdio", host: str = "127.0.0.1", port: int | None = None) -> None:
        """启动 MCP Server.
        
        Args:
            transport: "stdio" 或 "http"
            host: HTTP 模式绑定的主机
            port: HTTP 模式绑定的端口
        """
        if transport == "stdio":
            self.run_stdio()
        elif transport == "http":
            self.run_http(host, port)
        else:
            raise ValueError(f"不支持的传输模式: {transport}")
    
    @classmethod
    def main(cls) -> None:
        """命令行入口."""
        parser = argparse.ArgumentParser(description=f"{cls.display_name or cls.name} MCP Server")
        parser.add_argument(
            "--transport",
            choices=["stdio", "http"],
            default="stdio",
            help="传输模式 (默认: stdio)"
        )
        parser.add_argument(
            "--host",
            default="127.0.0.1",
            help="HTTP 模式主机 (默认: 127.0.0.1)"
        )
        parser.add_argument(
            "--port",
            type=int,
            default=None,
            help="HTTP 模式端口 (默认: 自动分配)"
        )
        parser.add_argument(
            "--info",
            action="store_true",
            help="打印 Skill 信息并退出"
        )
        
        args = parser.parse_args()
        
        server = cls()
        
        if args.info:
            print(json.dumps(server.get_info(), ensure_ascii=False, indent=2))
            sys.exit(0)
        
        print(f"启动 {cls.display_name or cls.name} MCP Server ({args.transport} 模式)...", file=sys.stderr)
        server.run(transport=args.transport, host=args.host, port=args.port)

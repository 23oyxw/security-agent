"""MCP client session — bridges Agent brain to MCP server tools."""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from security_agent import config


class MCPToolExecutor:
    def __init__(self):
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def connect(self, server_script: str | None = None) -> list[str]:
        import os
        import shutil

        env = os.environ.copy()
        root = str(config.PROJECT_ROOT)
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")

        if server_script:
            args = [server_script]
            cmd = config.python_executable()
        else:
            uv = shutil.which("uv") or "/home/oy0/.local/bin/uv"
            if os.path.isfile(uv):
                cmd, args = uv, ["run", "python", "-m", "security_agent.mcp.server"]
                env = None  # uv 自行管理环境
            else:
                cmd = config.python_executable()
                args = ["-m", "security_agent.mcp.server"]

        params = StdioServerParameters(
            command=cmd,
            args=args,
            env=env,
            cwd=root,
        )
        transport = await self._stack.enter_async_context(stdio_client(params))
        read_stream, write_stream = transport
        self._session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()
        tools = await self._session.list_tools()
        return [t.name for t in tools.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> str:
        if not self._session:
            raise RuntimeError("MCP 未连接，请先 connect()")
        result = await self._session.call_tool(name, arguments or {})
        if result.isError:
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.append(str(block))
            return "工具错误: " + "\n".join(parts) or "未知错误"
        if not result.content:
            return ""
        texts = []
        for block in result.content:
            if hasattr(block, "text"):
                texts.append(block.text)
            else:
                texts.append(str(block))
        return "\n".join(texts)

    async def close(self) -> None:
        await self._stack.aclose()
        self._session = None

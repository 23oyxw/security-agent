"""MCP Server — 从 registry 暴露全部工具."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from security_agent.tools.registry import TOOL_REGISTRY

mcp = FastMCP("SecurityAgentServer")


def _bind_tool(name: str, description: str, fn: Callable[..., Any]) -> None:
    """按函数签名动态注册 FastMCP 工具."""
    sig = inspect.signature(fn)
    params = [
        p
        for p in sig.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]

    if not params:

        @mcp.tool(name=name, description=description)
        async def _wrapped() -> str:
            result = fn()
            if inspect.isawaitable(result):
                result = await result
            return str(result)

        return

    # 单参数或带默认值 — 用显式包装
    ann = {p.name: p.annotation for p in params if p.annotation != inspect.Parameter.empty}
    ann["return"] = str

    async def _dynamic(**kwargs: Any) -> str:
        result = fn(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return str(result)

    _dynamic.__name__ = name
    _dynamic.__doc__ = description
    hints = {k: v for k, v in ann.items() if k != "return"}
    _dynamic.__annotations__ = hints
    mcp.tool(name=name, description=description)(_dynamic)


for _name, (_desc, _schema, _fn) in TOOL_REGISTRY.items():
    _bind_tool(_name, _desc, _fn)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

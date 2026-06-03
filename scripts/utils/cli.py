#!/usr/bin/env python3
"""CLI — 终端对话模式（可选 MCP 远程工具）."""

from __future__ import annotations

import argparse
import asyncio
import sys

from security_agent.agent.brain import AgentBrain
from security_agent.mcp.client import MCPToolExecutor


async def run_chat(use_mcp: bool) -> None:
    executor = None
    mcp_client = None
    if use_mcp:
        mcp_client = MCPToolExecutor()
        names = await mcp_client.connect()
        print("MCP 已连接，工具:", names)
        executor = mcp_client

    brain = AgentBrain(executor=executor)
    print("安全运维 Agent 已启动，输入 quit 退出\n")
    try:
        while True:
            try:
                query = input("你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not query or query.lower() in {"quit", "exit", "q"}:
                break
            result = await brain.chat(query)
            print(f"\nAgent: {result['reply']}\n")
            if result.get("tool_trace"):
                for t in result["tool_trace"]:
                    print(f"  [工具] {t['tool']}")
    finally:
        if mcp_client:
            await mcp_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="安全运维 Agent CLI")
    parser.add_argument("--mcp", action="store_true", help="通过 MCP Server 调用工具")
    args = parser.parse_args()
    try:
        asyncio.run(run_chat(args.mcp))
    except ValueError as exc:
        print(f"启动失败: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

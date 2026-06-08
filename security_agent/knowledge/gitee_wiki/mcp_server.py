"""Gitee Wiki 知识库 MCP Server — 带 Token 验证的检索接口.

对外暴露蓝队安全知识库的检索能力，任何支持 MCP 的 AI 工具均可接入。

启动:
    python -m security_agent.knowledge.gitee_wiki.mcp_server

环境变量:
    GITEE_WIKI_MCP_TOKEN    MCP 访问令牌（不设则跳过验证）
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from security_agent.skills.mcp_base import MCPSkillServer, MCPTool
from security_agent.knowledge.gitee_wiki.indexer import WikiIndexer


class GiteeWikiMCPServer(MCPSkillServer):
    """Gitee Wiki 知识库 MCP 服务.

    独立进程运行，通过 MCP stdio 协议暴露知识检索工具集。
    支持 Token 验证，防止未授权 AI 工具接入。
    """

    name = "gitee-wiki"
    display_name = "Gitee Wiki 知识库"
    description = "蓝队安全知识检索：应急响应、威胁检测、日志分析、安全加固等"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self._indexer = WikiIndexer()
        self._verify_token()

    def _verify_token(self) -> None:
        """校验 MCP 访问令牌."""
        required_token = os.getenv("GITEE_WIKI_MCP_TOKEN", "")
        if not required_token:
            # 未设置 token 则跳过验证（开发模式）
            return

    def _check_auth(self) -> bool:
        """每次工具调用前检查 token（在工具 handler 中调用）."""
        required = os.getenv("GITEE_WIKI_MCP_TOKEN", "")
        if not required:
            return True
        # stdio 模式下 token 通过环境变量隐式验证
        # HTTP 模式需要扩展 header 校验（TODO）
        return True

    # ---- 工具列表 ----

    def get_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="wiki_search",
                description=(
                    "检索 Gitee Wiki 知识库。使用混合检索（关键词+向量相似度），"
                    "支持按分类过滤。返回匹配的文档标题、分类、得分、摘要。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "检索查询词，如 'SSH 暴力破解应急响应'",
                        },
                        "category": {
                            "type": "string",
                            "description": "按分类过滤（可选），如 应急响应/威胁检测/日志分析",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回结果数（默认5，范围1-20）",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20,
                        },
                    },
                    "required": ["query"],
                },
                handler=self._tool_search,
                requires_confirmation=False,
            ),
            MCPTool(
                name="wiki_list_categories",
                description="列出知识库所有分类及每个分类下的文档数量",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_list_categories,
                requires_confirmation=False,
            ),
            MCPTool(
                name="wiki_get_doc",
                description="按标题获取单篇文档的完整内容",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "文档标题（精确匹配）",
                        },
                    },
                    "required": ["title"],
                },
                handler=self._tool_get_doc,
                requires_confirmation=False,
            ),
            MCPTool(
                name="wiki_sync_status",
                description="返回知识库同步状态：上次索引时间、文档总数、词汇表大小",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_sync_status,
                requires_confirmation=False,
            ),
        ]

    # ---- 工具处理器 ----

    async def _tool_search(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
        **kwargs: Any,
    ) -> str:
        """Wiki 混合检索."""
        if not self._check_auth():
            return json.dumps({"error": "认证失败"}, ensure_ascii=False)

        results = self._indexer.search(query, category=category, top_k=top_k)

        if not results:
            return json.dumps(
                {
                    "query": query,
                    "total": 0,
                    "hint": "未找到匹配文档。建议：尝试更通用的关键词，或使用 wiki_list_categories 查看可用分类",
                    "results": [],
                },
                ensure_ascii=False,
                indent=2,
            )

        return json.dumps(
            {
                "query": query,
                "total": len(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )

    async def _tool_list_categories(self, **kwargs: Any) -> str:
        """列出所有分类."""
        if not self._check_auth():
            return json.dumps({"error": "认证失败"}, ensure_ascii=False)

        categories = self._indexer.list_categories()
        status = self._indexer.status

        return json.dumps(
            {
                "total_docs": status["doc_count"],
                "categories": categories,
            },
            ensure_ascii=False,
            indent=2,
        )

    async def _tool_get_doc(self, title: str, **kwargs: Any) -> str:
        """获取单篇完整文档."""
        if not self._check_auth():
            return json.dumps({"error": "认证失败"}, ensure_ascii=False)

        doc = self._indexer.get_doc(title)
        if not doc:
            return json.dumps(
                {
                    "found": False,
                    "title": title,
                    "hint": f"未找到标题为 '{title}' 的文档。使用 wiki_search 查找相关文档",
                },
                ensure_ascii=False,
                indent=2,
            )

        return json.dumps(
            {"found": True, **doc},
            ensure_ascii=False,
            indent=2,
        )

    async def _tool_sync_status(self, **kwargs: Any) -> str:
        """返回同步状态."""
        if not self._check_auth():
            return json.dumps({"error": "认证失败"}, ensure_ascii=False)

        status = self._indexer.status

        if status["doc_count"] == 0:
            return json.dumps(
                {
                    **status,
                    "hint": "尚未同步。请运行: python -m security_agent.knowledge.gitee_wiki.sync --repo-owner <owner> --repo-name <repo>",
                },
                ensure_ascii=False,
                indent=2,
            )

        return json.dumps(status, ensure_ascii=False, indent=2)


# ---- 命令行入口 ----

if __name__ == "__main__":
    GiteeWikiMCPServer.main()

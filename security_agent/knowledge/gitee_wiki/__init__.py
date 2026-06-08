"""Gitee Wiki 知识库 — 解耦的知识检索层.

将蓝队安全知识从硬编码的 playbooks.py 解耦到 Gitee Wiki，
通过 MCP 协议对外暴露检索能力。支持 Token 验证、本地向量索引、
混合检索（关键词+余弦相似度）。

模块结构:
    models.py       WikiDoc 数据模型
    wiki_client.py  Gitee API v5 客户端
    indexer.py      向量索引生成 & 混合检索
    sync.py         定时同步脚本 (CLI + Python API)
    mcp_server.py   MCP Server (4 个检索工具)

典型工作流:
    1. 在 Gitee Wiki 编辑知识文档（Markdown + frontmatter）
    2. 运行 sync.py 拉取 → 本地缓存 + 向量索引
    3. 启动 mcp_server.py → AI 工具通过 MCP 协议检索
"""

from security_agent.knowledge.gitee_wiki.models import WikiDoc
from security_agent.knowledge.gitee_wiki.indexer import (
    WikiIndexer,
    save_cache,
    load_cache,
)
from security_agent.knowledge.gitee_wiki.wiki_client import GiteeWikiClient
from security_agent.knowledge.gitee_wiki.sync import sync_wiki

__all__ = [
    "WikiDoc",
    "WikiIndexer",
    "GiteeWikiClient",
    "sync_wiki",
    "save_cache",
    "load_cache",
]

"""Gitee Wiki 同步脚本 — 拉取 Wiki → 本地缓存 → 向量索引.

用法:
    # CLI 同步
    python -m security_agent.knowledge.gitee_wiki.sync \
        --repo-owner myorg --repo-name myrepo

    # 代码调用
    import asyncio
    from security_agent.knowledge.gitee_wiki.sync import sync_wiki
    count = asyncio.run(sync_wiki("myorg", "myrepo"))

环境变量:
    GITEE_API_TOKEN      Gitee 个人访问令牌 (必需)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

from security_agent.knowledge.gitee_wiki.indexer import (
    WikiIndexer,
    save_cache,
    load_cache,
)
from security_agent.knowledge.gitee_wiki.wiki_client import GiteeWikiClient

logger = logging.getLogger(__name__)


async def sync_wiki(
    repo_owner: str,
    repo_name: str,
    *,
    token: str | None = None,
    incremental: bool = False,
) -> dict[str, object]:
    """从 Gitee Wiki 全量拉取 → 生成本地缓存 + 向量索引.

    Args:
        repo_owner: Gitee 仓库所有者
        repo_name: 仓库名称
        token: Gitee API token（默认读 GITEE_API_TOKEN 环境变量）
        incremental: 增量更新（暂未实现，保留参数）

    Returns:
        {"doc_count": int, "synced_at": str, "errors": [...]}
    """
    start = time.time()
    errors: list[str] = []

    if not token:
        token = os.getenv("GITEE_API_TOKEN", "")

    if not token:
        return {
            "doc_count": 0,
            "synced_at": "",
            "error": "GITEE_API_TOKEN 未设置，无法访问 Gitee API",
        }

    client = GiteeWikiClient(token=token)

    try:
        pages = await client.fetch_wiki_list(repo_owner, repo_name)
    except Exception as e:
        logger.error("获取 Wiki 页面列表失败: %s", e)
        return {"doc_count": 0, "synced_at": "", "error": str(e)}

    if not pages:
        logger.warning(
            "Wiki 仓库 %s/%s 无页面（可能未初始化 Wiki）", repo_owner, repo_name
        )
        return {
            "doc_count": 0,
            "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "error": "Wiki 无页面",
        }

    docs = []
    for page in pages:
        slug = page["slug"]
        source_url = page.get("wiki_url", "")
        try:
            md = await client.fetch_wiki_page(repo_owner, repo_name, slug)
            doc = client.parse_wiki_content(md, source_url=source_url)
            docs.append(doc)
            logger.info("  ✓ %s [%s]", doc.title, doc.category)
        except Exception as e:
            msg = f"拉取页面 {slug} 失败: {e}"
            errors.append(msg)
            logger.warning("  ✗ %s", msg)

    if not docs:
        return {
            "doc_count": 0,
            "synced_at": "",
            "errors": errors,
        }

    # 保存缓存
    save_cache(docs)

    # 构建索引
    indexer = WikiIndexer()
    indexer.build_index(docs)

    elapsed = time.time() - start
    synced_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    logger.info(
        "同步完成: %d 篇文档, 耗时 %.1fs, %d 个错误",
        len(docs),
        elapsed,
        len(errors),
    )

    return {
        "doc_count": len(docs),
        "synced_at": synced_at,
        "errors": errors,
        "elapsed_sec": round(elapsed, 1),
    }


# ---- CLI ----

def main():
    parser = argparse.ArgumentParser(
        description="Gitee Wiki → 本地缓存 + 向量索引同步工具"
    )
    parser.add_argument(
        "--repo-owner", required=True, help="Gitee 仓库所有者 (用户名/组织名)"
    )
    parser.add_argument(
        "--repo-name", required=True, help="Gitee 仓库名"
    )
    parser.add_argument(
        "--token", default=None, help="Gitee API token（默认读环境变量 GITEE_API_TOKEN）"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="详细输出"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    result = asyncio.run(
        sync_wiki(args.repo_owner, args.repo_name, token=args.token)
    )

    if result.get("error"):
        print(f"❌ 同步失败: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ 同步完成: {result['doc_count']} 篇文档, 时间 {result['synced_at']}")
    if result.get("errors"):
        for e in result["errors"]:
            print(f"  ⚠️ {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()

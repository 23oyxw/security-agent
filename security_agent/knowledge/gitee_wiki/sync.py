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
import json
import logging
import os
import sys
import time
from pathlib import Path

from security_agent import config
from security_agent.knowledge.gitee_wiki.models import WikiDoc
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


# ---- 本地 Wiki 包同步（GitHub/Gitee 同源 Markdown，无需 Token）----

SYNC_META_PATH = config.DATA_DIR / "wiki_sync_meta.json"
WIKI_EXPORT_DIR = config.DATA_DIR / "wiki_export"


def _wiki_doc_from_md(path: Path) -> WikiDoc | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    title = path.stem
    category = "架构文档"
    if "boundary" in path.stem:
        category = "边界对抗集"
    elif path.stem.upper().startswith("T"):
        category = "架构分层"
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return WikiDoc(
        title=title,
        category=category,
        tags=[path.stem],
        content=text,
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        source_url=f"wiki://{path.stem}",
    )


def collect_local_wiki_docs(*, include_seed: bool = True) -> list[WikiDoc]:
    from security_agent.demo.boundary import boundary_wiki_path, export_boundary_to_wiki

    docs: list[WikiDoc] = []
    seen: set[str] = set()

    def add(doc: WikiDoc) -> None:
        if doc.title in seen:
            return
        seen.add(doc.title)
        docs.append(doc)

    if WIKI_EXPORT_DIR.is_dir():
        for path in sorted(WIKI_EXPORT_DIR.glob("*.md")):
            doc = _wiki_doc_from_md(path)
            if doc:
                add(doc)

    try:
        export_boundary_to_wiki()
        bp = boundary_wiki_path()
        if bp.exists():
            doc = _wiki_doc_from_md(bp)
            if doc:
                doc.category = "边界对抗集"
                add(doc)
    except Exception as e:
        logger.warning("边界 Wiki 导出失败: %s", e)

    if include_seed:
        try:
            from security_agent.knowledge.gitee_wiki.seed_knowledge import PRESET_DOCS
            for doc in PRESET_DOCS:
                add(doc)
        except Exception as e:
            logger.warning("种子知识加载失败: %s", e)

    return docs


def sync_local_wiki_bundle(*, include_seed: bool = True) -> dict[str, object]:
    start = time.time()
    docs = collect_local_wiki_docs(include_seed=include_seed)
    if not docs:
        return {"ok": False, "source": "local_bundle", "doc_count": 0, "error": "无 Wiki 文档"}

    save_cache(docs)
    indexer = WikiIndexer()
    indexer.build_index(docs)

    synced_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta = {
        "ok": True,
        "source": "local_bundle",
        "synced_at": synced_at,
        "doc_count": len(docs),
        "categories": indexer.list_categories(),
        "elapsed_sec": round(time.time() - start, 1),
        "wiki_export_dir": str(WIKI_EXPORT_DIR),
    }
    SYNC_META_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNC_META_PATH.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return meta


async def sync_wiki_hybrid(
    *,
    repo_owner: str | None = None,
    repo_name: str | None = None,
    include_seed: bool = True,
) -> dict[str, object]:
    owner = repo_owner or os.getenv("GITEE_WIKI_OWNER", "")
    repo = repo_name or os.getenv("GITEE_WIKI_REPO", "security-agent")
    token = os.getenv("GITEE_API_TOKEN", "")

    if token and owner:
        remote = await sync_wiki(owner, repo, token=token)
        if remote.get("doc_count", 0) > 0:
            from security_agent.demo.boundary import export_boundary_to_wiki

            export_boundary_to_wiki()
            return {
                "ok": True,
                "source": "gitee",
                "doc_count": remote.get("doc_count"),
                "synced_at": remote.get("synced_at"),
                "gitee": remote,
            }

    local = sync_local_wiki_bundle(include_seed=include_seed)
    local["fallback"] = "未配置 Gitee Token 或远程为空，已用本地 wiki_export + 种子"
    return local


def get_wiki_sync_status() -> dict[str, object]:
    import json

    from security_agent.demo.boundary import boundary_wiki_path

    indexer = WikiIndexer()
    loaded = indexer.load()
    meta: dict[str, object] = {}
    if SYNC_META_PATH.exists():
        try:
            meta = json.loads(SYNC_META_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}

    bp = boundary_wiki_path()
    boundary_info = {"exists": bp.exists(), "path": str(bp)}
    if bp.exists():
        text = bp.read_text(encoding="utf-8")
        boundary_info["matrix_cases"] = text.count("| T-") + text.count("| TOOL-")
        boundary_info["probe_count"] = text.count("| PE-")

    return {
        "index_loaded": loaded,
        "index": indexer.status if loaded else {"doc_count": 0},
        "last_sync": meta,
        "boundary": boundary_info,
        "wiki_export_dir": str(WIKI_EXPORT_DIR),
    }

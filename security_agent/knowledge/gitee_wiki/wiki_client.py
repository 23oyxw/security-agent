"""Gitee API v5 客户端 — 拉取 Wiki 内容.

使用 Gitee OpenAPI v5 读写仓库 Wiki 页面。
认证: Authorization: Bearer <GITEE_API_TOKEN>

API 文档: https://gitee.com/api/v5/swagger
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

from security_agent.knowledge.gitee_wiki.models import WikiDoc

logger = logging.getLogger(__name__)

GITEE_API_BASE = "https://gitee.com/api/v5"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TAG_LIST_RE = re.compile(r"\[([^\]]*)\]")


def _parse_yaml_frontmatter(text: str) -> dict[str, Any]:
    """从 Markdown frontmatter 提取结构化字段."""
    meta: dict[str, Any] = {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return meta
    raw = m.group(1)
    for line in raw.strip().split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if not key or not val:
            continue

        # tags 列表: [ssh, bruteforce, pam]
        if key == "tags":
            tag_match = _TAG_LIST_RE.search(val)
            if tag_match:
                meta[key] = [t.strip().strip("'\"") for t in tag_match.group(1).split(",") if t.strip()]
            else:
                meta[key] = [t.strip() for t in val.split(",") if t.strip()]
        else:
            # 去掉值的引号
            meta[key] = val.strip("'\"")

    return meta


class GiteeWikiClient:
    """Gitee Wiki API 客户端.

    用法:
        client = GiteeWikiClient(token="xxx")
        pages = await client.fetch_wiki_list("owner", "repo")
        md = await client.fetch_wiki_page("owner", "repo", "page-slug")
        doc = client.parse_wiki_content(md)
    """

    def __init__(self, token: str | None = None):
        self._token = token or os.getenv("GITEE_API_TOKEN", "")
        self._headers = {
            "Accept": "application/json",
            "User-Agent": "security-agent-gitee-wiki/1.0",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    async def _get(self, path: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        """GET 请求 Gitee API."""
        url = f"{GITEE_API_BASE}{path}" if not path.startswith("http") else path
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers, **kwargs)
            resp.raise_for_status()
            return resp.json()

    # ---- Wiki 页面列表 ----

    async def fetch_wiki_list(
        self, repo_owner: str, repo_name: str
    ) -> list[dict[str, Any]]:
        """获取仓库 Wiki 页面列表.

        Gitee API v5 没有专门的 wiki list 端点，使用仓库内容 API
        读取 .gitee/wiki/ 目录作为替代，或通过 repos/{owner}/{repo}/pages 获取。

        优先使用 pages API (Gitee Pages/Blog 功能)，若不可用则
        尝试通过 git tree API 读取 wiki 分支。
        """
        # 方案 A: Gitee 仓库 pages/builds API（仅限 Gitee Pages 功能）
        # 方案 B: 通过 git API 读取 wiki 仓库
        # 使用仓库 API: GET /repos/{owner}/{repo} 获取 has_wiki 状态
        # 然后通过 git data API 读取 wiki 内容

        wiki_repo_name = f"{repo_owner}/{repo_name}.wiki"
        try:
            # 尝试直接访问 wiki 仓库
            repo_info = await self._get(f"/repos/{repo_owner}/{repo_name}")
            if not repo_info.get("has_wiki"):
                logger.warning("仓库 %s/%s 未启用 Wiki", repo_owner, repo_name)
                return []

            # 通过 wiki 仓库的 git trees API 读取页面列表
            # wiki 仓库路径: {owner}/{repo}.wiki
            # 先获取默认分支的 tree
            branches = await self._get(
                f"/repos/{repo_owner}/{repo_name}.wiki/branches"
            )
            default_branch = "master"
            if isinstance(branches, list) and branches:
                default_branch = branches[0].get("name", "master")

            # 获取 tree sha
            branch_info = await self._get(
                f"/repos/{repo_owner}/{repo_name}.wiki/branches/{default_branch}"
            )
            commit_sha = (
                branch_info.get("commit", {}).get("sha", "")
                if isinstance(branch_info, dict)
                else ""
            )
            if not commit_sha:
                return []

            # 获取 commit 的 tree
            commit = await self._get(
                f"/repos/{repo_owner}/{repo_name}.wiki/git/commits/{commit_sha}"
            )
            tree_sha = (
                commit.get("tree", {}).get("sha", "")
                if isinstance(commit, dict)
                else ""
            )
            if not tree_sha:
                return []

            # 递归获取 tree 中的 .md 文件
            tree = await self._get(
                f"/repos/{repo_owner}/{repo_name}.wiki/git/trees/{tree_sha}",
                params={"recursive": 1},
            )
            if not isinstance(tree, dict):
                return []

            pages = []
            for item in tree.get("tree", []):
                name = item.get("path", "")
                if name.endswith(".md") or name.endswith(".markdown"):
                    slug = name.rsplit(".", 1)[0]
                    pages.append({
                        "name": name,
                        "slug": slug,
                        "sha": item.get("sha", ""),
                        "wiki_url": (
                            f"https://gitee.com/{repo_owner}/{repo_name}/wiki/{slug}"
                        ),
                    })

            logger.info("Wiki 仓库 %s/wiki: 发现 %d 个页面", repo_name, len(pages))
            return pages

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Wiki 仓库 %s 不存在或未初始化", wiki_repo_name
                )
                return []
            raise

    # ---- Wiki 页面内容 ----

    async def fetch_wiki_page(
        self, repo_owner: str, repo_name: str, page_slug: str
    ) -> str:
        """获取单个 Wiki 页面的 Markdown 内容.

        通过 Gitee git API 读取 .wiki 仓库中的原始文件.
        """
        wiki_repo_name = f"{repo_owner}/{repo_name}.wiki"

        # 先获取文件列表找到对应的 sha
        branches = await self._get(
            f"/repos/{repo_owner}/{repo_name}.wiki/branches"
        )
        default_branch = "master"
        if isinstance(branches, list) and branches:
            default_branch = branches[0].get("name", "master")

        branch_info = await self._get(
            f"/repos/{repo_owner}/{repo_name}.wiki/branches/{default_branch}"
        )
        commit_sha = (
            branch_info.get("commit", {}).get("sha", "")
            if isinstance(branch_info, dict)
            else ""
        )
        if not commit_sha:
            raise ValueError(f"无法获取 wiki 分支 {default_branch} 的 commit")

        commit = await self._get(
            f"/repos/{repo_owner}/{repo_name}.wiki/git/commits/{commit_sha}"
        )
        tree_sha = (
            commit.get("tree", {}).get("sha", "")
            if isinstance(commit, dict)
            else ""
        )
        if not tree_sha:
            raise ValueError("无法获取 wiki tree")

        tree = await self._get(
            f"/repos/{repo_owner}/{repo_name}.wiki/git/trees/{tree_sha}",
            params={"recursive": 1},
        )
        if not isinstance(tree, dict):
            raise ValueError("无效的 tree 响应")

        # 找到匹配的 .md 文件
        target_sha = None
        for item in tree.get("tree", []):
            name = item.get("path", "")
            if name == f"{page_slug}.md" or name == f"{page_slug}.markdown":
                target_sha = item.get("sha", "")
                break
            if name == f"{page_slug}":
                target_sha = item.get("sha", "")
                break

        if not target_sha:
            raise ValueError(f"Wiki 页面不存在: {page_slug}")

        # 获取 blob 内容 (Base64 编码)
        blob = await self._get(
            f"/repos/{repo_owner}/{repo_name}.wiki/git/blobs/{target_sha}"
        )
        if not isinstance(blob, dict):
            raise ValueError(f"无效的 blob 响应: {page_slug}")

        import base64
        content_b64 = blob.get("content", "")
        if not content_b64:
            return ""

        try:
            return base64.b64decode(content_b64).decode("utf-8")
        except Exception:
            return ""

    # ---- Frontmatter 解析 ----

    def parse_wiki_content(self, markdown_text: str, source_url: str = "") -> WikiDoc:
        """从 Markdown + frontmatter 提取结构化 WikiDoc.

        Wiki 文档约定格式:
            ---
            title: Linux SSH 暴力破解应急响应
            category: 应急响应
            tags: [ssh, bruteforce, pam, fail2ban]
            updated_at: 2026-06-08
            ---

            ## 检测方法
            ...
        """
        meta = _parse_yaml_frontmatter(markdown_text)

        # 正文：去掉 frontmatter 块
        body = _FRONTMATTER_RE.sub("", markdown_text).strip()

        title = meta.get("title", "未命名文档")
        return WikiDoc(
            title=title,
            category=meta.get("category", "未分类"),
            tags=meta.get("tags", []),
            content=body,
            updated_at=meta.get("updated_at", ""),
            source_url=source_url,
        )

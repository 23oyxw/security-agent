#!/usr/bin/env python3
"""推送项目文档到 Gitee Wiki — v0.9.0 双向知识同步.

用法:
    # 设置 GITEE_API_TOKEN 环境变量后运行
    set GITEE_API_TOKEN=your_token
    python scripts/push_gitee_wiki.py

    # 或直接传参
    python scripts/push_gitee_wiki.py --token your_token --owner swok --repo security-agent
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 要推送的文档: {Wiki页面标题: 本地文件路径}
DOCS_TO_PUSH: dict[str, str] = {
    "Home": "docs/INDEX.md",
    "架构-终版架构": "docs/architecture/FINAL_ARCHITECTURE.md",
    "架构-五层流水线": "docs/architecture/FIVE_LAYER_PIPELINE.md",
    "架构-三方统一契约": "docs/architecture/TRIPLE_UNIFY.md",
    "架构-体验驱动设计": "docs/architecture/EXPERIENCE_DRIVEN_DESIGN.md",
    "架构-生产级升级方案": "docs/architecture/FULL_DOMAIN_UPGRADE.md",
    "架构-总结与v1.0计划": "docs/architecture/V0_9_REVIEW_AND_V1_0_PLAN.md",
    "部署-麒麟LoongArch": "docs/DEPLOY_KYLIN_LOONGARCH.md",
    "部署-Windows": "docs/deploy/WINDOWS.md",
    "竞赛-官方缺口分析": "docs/competitions/A2_OFFICIAL_GAP_ANALYSIS.md",
    "竞赛-标准与完成度": "docs/competitions/A2_STANDARDS_AND_COMPLETION.md",
    "竞赛-提交清单": "docs/competitions/SUBMISSION_CHECKLIST.md",
    "竞赛-演示脚本": "docs/competitions/DEMO_SCRIPT.md",
    "开发-仓库结构": "docs/REPO_STRUCTURE.md",
    "开发-版本发布": "docs/RELEASE.md",
}


def main():
    parser = argparse.ArgumentParser(description="推送文档到 Gitee Wiki")
    parser.add_argument("--token", default=os.getenv("GITEE_API_TOKEN", ""))
    parser.add_argument("--owner", default="swok")
    parser.add_argument("--repo", default="security-agent")
    parser.add_argument("--dry-run", action="store_true", help="只预览不推送")
    args = parser.parse_args()

    if not args.token and not args.dry_run:
        print("请设置 GITEE_API_TOKEN 环境变量或通过 --token 传入")
        print("获取 Token: https://gitee.com/profile/personal_access_tokens")
        print("权限: projects")
        sys.exit(1)

    print(f"目标: https://gitee.com/{args.owner}/{args.repo}/wiki")
    print(f"文档数: {len(DOCS_TO_PUSH)}")
    print()

    docs_loaded = {}
    for title, rel_path in DOCS_TO_PUSH.items():
        file_path = ROOT / rel_path
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            # 添加 frontmatter
            content = f"---\ntitle: {title}\nupdated_at: 2026-07-13\n---\n\n{content}"
            docs_loaded[title] = content
            print(f"  LOADED: {title} ({len(content)} chars)")
        else:
            print(f"  MISSING: {title} ({rel_path})")

    if args.dry_run:
        print(f"\n[DRY RUN] 将推送 {len(docs_loaded)} 个页面到 Gitee Wiki")
        return

    if not docs_loaded:
        print("没有文档可推送")
        return

    print(f"\n推送 {len(docs_loaded)} 个页面...")

    import asyncio
    from security_agent.knowledge.gitee_wiki.wiki_client import GiteeWikiClient

    async def push():
        client = GiteeWikiClient(token=args.token)
        results = await client.push_docs(args.owner, args.repo, docs_loaded)
        return results

    results = asyncio.run(push())

    print(f"\n结果: {results['pushed']} 成功, {results['failed']} 失败")
    if results["errors"]:
        for err in results["errors"]:
            print(f"  ERROR: {err}")

    print(f"\nWiki 地址: https://gitee.com/{args.owner}/{args.repo}/wiki")


if __name__ == "__main__":
    main()

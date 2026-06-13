"""L1 knowledge answer contract."""

from __future__ import annotations
from typing import Any


def format_knowledge_brief(
    refs: list[dict[str, Any]],
    *,
    max_bullets: int = 3,
) -> dict[str, Any]:
    bullets: list[dict[str, str]] = []
    sources: list[dict[str, str]] = []
    seen_src: set[str] = set()

    for ref in refs[:max_bullets]:
        title = str(ref.get("title") or ref.get("id") or "\u6761\u76ee")
        snippet = (ref.get("snippet") or ref.get("body") or "")[:160].strip()
        actions = ref.get("suggested_actions") or []
        action_hint = ("\uff1b\u5efa\u8bae\uff1a" + actions[0]) if actions else ""
        bullets.append({
            "title": title,
            "text": f"{snippet}{action_hint}" if snippet else title,
            "source": str(ref.get("source") or "knowledge"),
            "score": str(ref.get("score") or ""),
        })
        src_key = f"{ref.get('source')}:{ref.get('id') or title}"
        if src_key not in seen_src:
            seen_src.add(src_key)
            sources.append({
                "id": str(ref.get("id") or ""),
                "title": title,
                "source": str(ref.get("source") or "knowledge"),
                "category": str(ref.get("category") or ""),
            })

    if not bullets:
        summary = "\u672a\u547d\u4e2d\u77e5\u8bc6\u5e93\uff1b\u8bf7\u8865\u5145\u5173\u952e\u8bcd\u6216\u67e5\u9605 Gitee Wiki / Playbook\u3002"
    else:
        summary = f"\u547d\u4e2d {len(refs)} \u6761\uff1b\u5c55\u793a\u524d {len(bullets)} \u6761\u8981\u70b9\uff08\u9644\u6765\u6e90\uff09\u3002"

    return {
        "summary": summary,
        "bullets": bullets,
        "sources": sources,
        "constraint": "\u53ea\u5f15\u7528\u4e0d\u6267\u884c",
        "format": "3-bullet + source",
    }
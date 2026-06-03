"""知识库路由 — 安全处置剧本检索与 RAG."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from security_agent.api.deps import get_current_user
from security_agent.api.models import KnowledgeSearchRequest
from security_agent.auth.models import User

router = APIRouter()


class KnowledgeRagRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    threat_tag: str | None = None
    include_grounding: bool = True


@router.post("/search")
async def search(req: KnowledgeSearchRequest, user: User = Depends(get_current_user)):
    """检索知识库（混合检索）"""
    from security_agent.retrieval.hybrid import search_knowledge

    hits = search_knowledge(req.query, top_k=req.top_k)
    results = [
        {
            "id": h["id"],
            "title": h["title"],
            "content": h["excerpt"],
            "score": h["score"],
            "source": "playbook",
            "severity": h.get("severity"),
            "threat_tags": h.get("threat_tags", []),
        }
        for h in hits
    ]
    return {"query": req.query, "results": results, "total": len(results)}


@router.post("/rag")
async def rag(req: KnowledgeRagRequest, user: User = Depends(get_current_user)):
    """RAG 检索 + grounding 上下文（供 Agent / Dify 回调）"""
    from security_agent.retrieval.hybrid import format_grounding_block, search_knowledge

    hits = search_knowledge(req.query, top_k=req.top_k, threat_tag=req.threat_tag)
    citations = [
        {
            "id": h["id"],
            "title": h["title"],
            "score": h["score"],
            "excerpt": h["excerpt"],
            "severity": h.get("severity"),
            "suggested_actions": h.get("suggested_actions", []),
        }
        for h in hits
    ]
    payload: dict = {"query": req.query, "citations": citations, "total": len(citations)}
    if req.include_grounding:
        payload["grounding"] = format_grounding_block(hits)
    return payload


@router.get("/playbooks")
async def list_playbooks(user: User = Depends(get_current_user)):
    """列出安全处置剧本"""
    try:
        from security_agent.knowledge.playbooks import PLAYBOOKS

        items = [
            {
                "id": p.id,
                "title": p.title,
                "category": p.threat_tags[0] if p.threat_tags else "general",
                "description": p.body[:200],
                "severity": p.severity,
                "content": p.body,
                "steps": "\n".join(p.suggested_actions),
                "do_not": list(p.do_not),
            }
            for p in PLAYBOOKS
        ]
        return {"playbooks": items, "total": len(items)}
    except Exception:
        return {"playbooks": [], "total": 0}


@router.get("/unified-search")
async def unified_knowledge_search(
    q: str = "",
    limit: int = 10,
    user: User = Depends(get_current_user),
):
    """统一知识库检索 — 同时搜索 Playbooks + 安全参考文档."""
    results = []
    q_lower = q.lower().strip()
    if not q_lower:
        return {"query": q, "total": 0, "results": []}

    q_tokens = [t for t in q_lower.split() if len(t) >= 2]

    # 1. 搜索 Playbooks
    try:
        from security_agent.knowledge.playbooks import PLAYBOOKS

        for pb in PLAYBOOKS:
            searchable = (
                pb.title + " " + pb.body + " "
                + " ".join(pb.keywords) + " "
                + " ".join(pb.suggested_actions) + " "
                + " ".join(pb.threat_tags)
            ).lower()
            score = sum(1 for t in q_tokens if t in searchable)
            if score > 0:
                results.append({
                    "id": pb.id,
                    "title": pb.title,
                    "body": pb.body,
                    "severity": pb.severity,
                    "threat_tags": list(pb.threat_tags),
                    "suggested_actions": list(pb.suggested_actions),
                    "do_not": list(pb.do_not),
                    "source": "playbook",
                    "_score": score * 2,
                })
    except Exception:
        pass

    # 2. 搜索安全参考文档
    import os

    doc_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "docs", "security", "BLUE_TEAM_DEFENSE_KNOWLEDGE.md"
    )
    doc_path = os.path.abspath(doc_path)
    if os.path.exists(doc_path):
        try:
            content = open(doc_path, encoding="utf-8").read()
            sections = []
            current_section = {"title": "前言", "content": ""}
            for line in content.split("\n"):
                if line.startswith("## "):
                    if current_section["content"].strip():
                        sections.append(current_section)
                    current_section = {"title": line[3:].strip(), "content": ""}
                else:
                    current_section["content"] += line + "\n"
            if current_section["content"].strip():
                sections.append(current_section)

            for sec in sections:
                sec_text = (sec["title"] + " " + sec["content"]).lower()
                score = sum(1 for t in q_tokens if t in sec_text)
                if score > 0:
                    excerpt = sec["content"][:300].strip()
                    results.append({
                        "id": "DOC-" + sec["title"][:20],
                        "title": "📄 " + sec["title"],
                        "body": excerpt,
                        "severity": "信息",
                        "threat_tags": ["文档"],
                        "suggested_actions": [],
                        "do_not": [],
                        "source": "document",
                        "_score": score,
                    })
        except Exception:
            pass

    results.sort(key=lambda x: x["_score"], reverse=True)
    return {"query": q, "total": len(results), "results": results[:limit]}

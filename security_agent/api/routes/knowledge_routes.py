"""知识库路由"""

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


@router.get("/blue-team/repos")
async def blue_team_repos(user: User = Depends(get_current_user)):
    """获取蓝队开源项目清单"""
    from security_agent.knowledge.blue_team_crawler import BlueTeamCrawler

    crawler = BlueTeamCrawler()
    return {"repos": crawler.list_repos()}


@router.post("/blue-team/scan")
async def blue_team_scan(user: User = Depends(get_current_user)):
    """扫描蓝队开源项目（LLM 分析 + 预设知识，不 clone）"""
    import asyncio
    from security_agent.knowledge.blue_team_crawler import BlueTeamCrawler

    crawler = BlueTeamCrawler()
    report = await asyncio.to_thread(crawler.run)
    return {
        "total_projects": len(report.projects),
        "total_skills": report.total_skills,
        "total_patches": report.total_patches,
        "total_scenarios": report.total_scenarios,
        "projects": [
            {
                "name": p.name,
                "category": p.category,
                "skills": p.blue_team_skills,
                "patches": p.optimization_patches,
                "scenarios": p.training_scenarios,
            }
            for p in report.projects
        ],
    }


@router.get("/blue-team/training")
async def blue_team_training(user: User = Depends(get_current_user)):
    """获取今日蓝队训练场景"""
    from security_agent.knowledge.blue_team_crawler import BlueTeamCrawler

    crawler = BlueTeamCrawler()
    return crawler.get_daily_training()


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
    """列出安全剧本"""
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
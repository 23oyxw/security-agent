"""L1 三感知独立路由 — 边界对抗 · 灵敏知识检索（analyze 只读）."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()


class BoundaryEvaluateRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    include_calibration: bool = True


class KnowledgeRetrieveRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=20)
    intent_hint: str | None = None


@router.post("/boundary/evaluate")
async def evaluate_boundary(req: BoundaryEvaluateRequest, user: User = Depends(get_current_user)):
    """L1 抗性边界感知 — 输入对抗评估 + 权限跃迁探针."""
    from security_agent.agent.l1_triple_perception import run_adversarial_boundary_perception

    block = await run_adversarial_boundary_perception(req.message)
    if not req.include_calibration:
        block = {**block, "adversarial_calibration": {"skipped": True}}
    return {
        "layer": "L1",
        "module": "adversarial_boundary",
        "message_preview": req.message[:200],
        **block,
    }


@router.get("/boundary/calibration")
async def boundary_calibration_matrix(user: User = Depends(get_current_user)):
    """对抗训练校准矩阵 — 101 条终端/工具边界用例."""
    from security_agent.demo.boundary import run_terminal_boundary_tests, summarize_boundary

    rows = run_terminal_boundary_tests()
    summary = summarize_boundary(rows)
    return {
        "layer": "L1",
        "module": "adversarial_calibration",
        "summary": summary,
        "rows": rows,
        "resistance_training": "权限跃迁阻力对抗训练集",
    }


@router.post("/knowledge/retrieve")
async def retrieve_knowledge(req: KnowledgeRetrieveRequest, user: User = Depends(get_current_user)):
    """L1 灵敏知识库检索 — hybrid + 意图扩展 + 灵敏度."""
    from security_agent.agent.l1_triple_perception import run_sensitive_knowledge_retrieval

    block = await run_sensitive_knowledge_retrieval(
        req.message,
        top_k=req.top_k,
        intent_hint=req.intent_hint,
    )
    return {
        "layer": "L1",
        "module": "sensitive_knowledge",
        "query": req.message[:200],
        **block,
    }

"""L2 Skill Flow REST — 薄胶水，编排逻辑在 skills/flows/runner.py."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from security_agent.api.deps import get_current_user, require_operator
from security_agent.auth.models import User
from security_agent.skills.flows import list_flows, run_skill_flow

router = APIRouter()


class SkillFlowRunRequest(BaseModel):
    context: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None


@router.get("/")
async def list_skill_flows(user: User = Depends(get_current_user)):
    """列出可用 L2 flow（secure_exec / alert_response / scan_report）."""
    return {"flows": list_flows(), "total": len(list_flows())}


@router.post("/{flow_name}/run")
async def run_flow(
    flow_name: str,
    req: SkillFlowRunRequest,
    user: User = Depends(require_operator),
):
    """执行命名 Skill Flow（需 operator）."""
    ctx = dict(req.context or {})
    ctx.setdefault("user", user.username)
    return await run_skill_flow(
        flow_name,
        ctx,
        trace_id=req.trace_id or "",
    )

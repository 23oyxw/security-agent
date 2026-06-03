"""只读工作流定义 — 答辩展示用."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()

_WORKFLOW_PATH = Path(__file__).resolve().parents[3] / "configs" / "workflows" / "autonomous_ops.json"


@router.get("/standard")
async def get_standard_workflow(user: User = Depends(get_current_user)):
    """返回预置运维流程 JSON（只读，非编辑器）."""
    if _WORKFLOW_PATH.is_file():
        return json.loads(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    return {"id": "empty", "title": "未配置", "steps": []}

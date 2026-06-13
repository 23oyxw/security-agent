"""Environment repair panel API."""

from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()

REPAIR_CATALOG = [
    {"id": "repair_disk", "title": "disk cleanup", "intent": "full_check", "message": "disk cleanup and security check", "sandbox_required": True},
    {"id": "repair_health", "title": "health repair", "intent": "health", "message": "system health and audit", "sandbox_required": False},
    {"id": "repair_scan", "title": "security scan", "intent": "scan", "message": "security scan", "sandbox_required": False},
    {"id": "repair_autonomous", "title": "autonomous repair", "intent": "autonomous", "message": "autonomous repair mission", "sandbox_required": True},
]

class RepairTriggerRequest(BaseModel):
    repair_id: str
    user_confirmed: bool = False

@router.get("/catalog")
async def repair_catalog(user: User = Depends(get_current_user)):
    return {"catalog": REPAIR_CATALOG, "layer": "L3"}

@router.get("/history")
async def repair_history(limit: int = 20, user: User = Depends(get_current_user)):
    try:
        from security_agent.storage.plan_store import get_plan_store
        rows = []
        for plan in get_plan_store().list_recent(limit=limit):
            if plan.get("intent") in ("full_check", "scan", "autonomous", "health"):
                rows.append({"plan_id": plan.get("plan_id"), "intent": plan.get("intent"), "status": plan.get("status"), "trace_id": plan.get("trace_id"), "l2_verdict": plan.get("l2_verdict")})
        return {"repairs": rows, "count": len(rows)}
    except Exception:
        return {"repairs": [], "count": 0}

@router.post("/trigger")
async def repair_trigger(req: RepairTriggerRequest, user: User = Depends(get_current_user)):
    item = next((x for x in REPAIR_CATALOG if x["id"] == req.repair_id), None)
    if not item:
        return {"ok": False, "error": "unknown repair_id"}
    from security_agent.api import agent_plan
    plan = await agent_plan.build_analysis_plan(item["message"])
    await agent_plan.run_l2_precheck(plan["plan_id"])
    plan = agent_plan.get_plan(plan["plan_id"]) or plan
    result = {"ok": True, "repair_id": req.repair_id, "plan_id": plan["plan_id"], "trace_id": plan.get("trace_id"), "l2_verdict": plan.get("l2_verdict"), "phase": "planned"}
    if plan.get("l2_verdict") == "deny":
        result["ok"] = False
        result["error"] = "L2 blocked"
        return result
    if (plan.get("l2_verdict") == "confirm" or plan.get("requires_confirm")) and not req.user_confirmed:
        result["needs_confirm"] = True
        return result
    try:
        ex = await agent_plan.execute_plan(plan["plan_id"], user_confirmed=True)
        result["phase"] = "executed"
        result["execute"] = {"trace_id": ex.get("trace_id")}
    except ValueError as e:
        result["ok"] = False
        result["error"] = str(e)
    return result
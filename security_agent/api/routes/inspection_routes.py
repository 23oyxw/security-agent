"""Inspection engine API."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()

class RunSuiteRequest(BaseModel):
    suite_id: str = "kylin_baseline"
    trace_id: str | None = None
    push_webhook: bool = True

@router.get("/catalog")
async def inspection_catalog(user: User = Depends(get_current_user)):
    from security_agent.inspection.suites import list_suite_ids
    from security_agent.notify.webhook import _load_config
    return {"engine": "huace-style-inspection", "layer": "L3-readonly", "suites": list_suite_ids(),
        "baseline": "data/baselines/kylin_v11.json",
        "webhook": {"enabled": bool(_load_config().get("enabled")), "config": "configs/notify_channels.yaml"},
        "scheduler": "scripts/scheduled_patrol.py inspection"}

@router.get("/suites")
async def list_inspection_suites(user: User = Depends(get_current_user)):
    from security_agent.inspection.runner import list_suites
    return {"suites": list_suites()}

@router.post("/run")
async def run_inspection(req: RunSuiteRequest, user: User = Depends(get_current_user)):
    from security_agent.inspection.runner import run_suite
    return await run_suite(req.suite_id, trace_id=req.trace_id, push_webhook=req.push_webhook)

@router.get("/reports/{suite_id}/latest")
async def latest_inspection_report(suite_id: str, user: User = Depends(get_current_user)):
    from security_agent.inspection.runner import get_latest_report
    report = get_latest_report(suite_id)
    if not report:
        return {"ok": False, "error": "no report"}
    return report

@router.get("/risk/predict")
async def predict_inspection_risk(user: User = Depends(get_current_user)):
    from security_agent.inspection.risk_window import predict_risk_window
    return predict_risk_window()

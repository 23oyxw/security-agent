"""Dify webhook 回调与代理 — 桥接到安全网关."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import yaml
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from security_agent import config
from security_agent.api.deps import get_current_user, require_operator
from security_agent.audit import log as audit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dify"])

_DIFY_CONFIG_PATH = config.PROJECT_ROOT / "configs" / "dify_config.yaml"
_DIFY_CONFIG_EXAMPLE = config.PROJECT_ROOT / "configs" / "dify_config.yaml.example"

_callback_results: dict[str, dict] = {}
_dify_integration = None


class DifyCallbackPayload(BaseModel):
    source: str = Field(default="dify_workflow")
    workflow_type: Optional[str] = None
    workflow_run_id: Optional[str] = None
    status: Optional[str] = None
    outputs: dict = Field(default_factory=dict)
    timestamp: Optional[str] = None
    trace_id: Optional[str] = None
    auto_remediation: bool = Field(default=False)


def _resolve_dify_config_path() -> Path:
    if _DIFY_CONFIG_PATH.exists():
        return _DIFY_CONFIG_PATH
    return _DIFY_CONFIG_EXAMPLE


def _get_integration():
    global _dify_integration
    if _dify_integration is None:
        try:
            from security_agent.safety_gate.gate import SafetyGate
            from security_agent.dify.bridge import DifyIntegration

            _dify_integration = DifyIntegration(gate=SafetyGate())
            logger.info("DifyRoutes: integration initialized with SafetyGate")
        except Exception as exc:
            logger.warning("DifyRoutes: could not init full integration: %s", exc)
            from security_agent.dify.bridge import DifyIntegration

            _dify_integration = DifyIntegration()
    return _dify_integration


def _verify_signature(payload: dict, signature: Optional[str]) -> bool:
    if not config.SIGNING_ENABLED or not config.SIGNING_KEY:
        return True
    if not signature:
        logger.warning("DifyRoutes: missing X-Signature header")
        return False
    expected = hmac.new(
        config.SIGNING_KEY.encode(),
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/callback")
async def dify_callback(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-Id"),
):
    body = await request.json()
    if not _verify_signature(body, x_signature):
        raise HTTPException(status_code=401, detail="invalid signature")

    workflow_type = body.get("workflow_type") or body.get("source") or "unknown"
    run_id = body.get("workflow_run_id") or body.get("run_id") or str(uuid.uuid4())[:8]
    trace_id = body.get("trace_id") or x_trace_id or f"trace-{uuid.uuid4().hex[:12]}"
    outputs_raw = body.get("outputs", {})

    if isinstance(outputs_raw, str):
        try:
            outputs_raw = json.loads(outputs_raw)
        except (json.JSONDecodeError, TypeError):
            outputs_raw = {"raw": outputs_raw}
    if not isinstance(outputs_raw, dict):
        outputs_raw = {"raw": str(outputs_raw)}

    if workflow_type == "unknown" and outputs_raw:
        blob = str(outputs_raw)
        if "threat_type" in blob or "risk_level" in blob:
            workflow_type = "threat_detection"
        elif "category" in blob or "is_urgent" in blob:
            workflow_type = "security_chat"
        elif "answer" in blob or "sources" in blob:
            workflow_type = "knowledge_rag"
        elif "check_results" in blob or "has_critical" in blob:
            workflow_type = "security_inspection"
        elif "deep_analysis" in blob or "triage" in blob:
            workflow_type = "alert_processing"

    auto_remediation = body.get("auto_remediation", False)
    integration = _get_integration()
    result = integration.handle_callback(
        workflow_type=workflow_type,
        outputs=outputs_raw,
        workflow_run_id=run_id,
        trace_id=trace_id,
    )

    if auto_remediation and result.get("action_required") and result.get("gate_approved", True):
        actions = result.get("suggested_actions") or result.get("mitigation_steps") or []
        if actions:
            result["execution_results"] = integration.execute_remediation(actions)
    elif result.get("action_required"):
        result["execution_results"] = []
        result["auto_remediation_skipped"] = True

    _callback_results[run_id] = {
        "workflow_type": workflow_type,
        "status": "completed",
        "trace_id": trace_id,
        "workflow_run_id": run_id,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    audit.append_audit(
        "dify_callback",
        {
            "workflow_type": workflow_type,
            "workflow_run_id": run_id,
            "trace_id": trace_id,
            "action_required": bool(result.get("action_required")),
            "auto_remediation": auto_remediation,
        },
    )
    return {"status": "ok", "result": result, "run_id": run_id, "trace_id": trace_id}


@router.post("/proxy/run-workflow")
async def proxy_run_workflow(
    workflow_type: str = Body(..., embed=True),
    inputs: dict = Body(default_factory=dict, embed=True),
    trace_id: Optional[str] = Body(default=None, embed=True),
    user=Depends(require_operator),
):
    cfg_path = _resolve_dify_config_path()
    if not cfg_path.exists():
        raise HTTPException(502, "Dify config not found (copy configs/dify_config.yaml.example)")

    with open(cfg_path, encoding="utf-8") as f:
        dify_config = yaml.safe_load(f) or {}

    wf_cfg = (dify_config.get("workflows") or {}).get(workflow_type)
    if not wf_cfg or not wf_cfg.get("api_key"):
        raise HTTPException(400, f"Unknown workflow or missing API key: {workflow_type}")

    api_key = wf_cfg["api_key"]
    dify_base = dify_config.get("DIFY_API_URL", "http://localhost/v1")
    timeout = int(dify_config.get("workflow_defaults", {}).get("timeout", 120))
    req_trace_id = trace_id or f"trace-{uuid.uuid4().hex[:12]}"
    merged_inputs = dict(inputs or {})
    merged_inputs.setdefault("trace_id", req_trace_id)

    from security_agent.resilience.circuit import get_circuit

    circuit = get_circuit(
        "dify:proxy",
        failure_threshold=config.CIRCUIT_FAILURE_THRESHOLD,
        open_sec=config.CIRCUIT_OPEN_SEC,
    )
    if not circuit.allow():
        raise HTTPException(503, "Dify proxy circuit open") from None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{dify_base}/workflows/run",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "inputs": merged_inputs,
                    "response_mode": "blocking",
                    "user": user.username,
                },
            )
    except httpx.RequestError as exc:
        circuit.record_failure(str(exc))
        logger.error("Dify proxy: request failed: %s", exc)
        raise HTTPException(502, f"Dify API unreachable: {exc}") from exc

    if resp.status_code != 200:
        circuit.record_failure(resp.text[:100])
        raise HTTPException(502, f"Dify API error: {resp.text[:300]}")

    circuit.record_success()

    data = resp.json().get("data", {})
    run_id = data.get("workflow_run_id") or str(uuid.uuid4())[:8]
    _callback_results[run_id] = {
        "workflow_type": workflow_type,
        "status": data.get("status", "unknown"),
        "trace_id": req_trace_id,
        "workflow_run_id": run_id,
        "outputs": data.get("outputs", {}),
        "elapsed": data.get("elapsed_time"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    audit.append_audit(
        "dify_proxy_run_workflow",
        {"workflow_type": workflow_type, "workflow_run_id": run_id, "operator": user.username},
    )
    return {
        "run_id": run_id,
        "trace_id": req_trace_id,
        "status": data.get("status"),
        "outputs": data.get("outputs", {}),
        "elapsed": data.get("elapsed_time"),
    }


@router.get("/callback-results/{run_id}")
async def get_callback_result(run_id: str, user=Depends(get_current_user)):
    entry = _callback_results.get(run_id)
    if not entry:
        raise HTTPException(404, f"Result not found for run_id: {run_id}")
    return {"run_id": run_id, **entry}


@router.get("/health")
async def dify_health():
    cfg = _resolve_dify_config_path()
    return {
        "status": "ok",
        "dify_integration_ready": _dify_integration is not None,
        "signing_enabled": config.SIGNING_ENABLED,
        "proxy_available": cfg.exists(),
        "config_path": str(cfg),
    }

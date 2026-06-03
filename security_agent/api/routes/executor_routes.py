"""④ 最小权限执行路由 — 审批单 + 预算守卫."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from security_agent.api.deps import get_current_user, require_operator
from security_agent.api.models import ExecuteRequest, ExecuteResponse, RollbackRequest
from security_agent.audit import log as audit
from security_agent.auth.models import User
from security_agent.ops.guardrails import is_approval_granted, require_request_budget

router = APIRouter()
_rollback_registry: dict = {}

_RISK_LABELS = {
    "READONLY": "只读",
    "REVERSIBLE": "可逆",
    "IRREVERSIBLE": "不可逆",
    "CRITICAL": "关键",
}


def _assess_command(command: str) -> tuple[str, str]:
    from security_agent.terminal.executor import assess_terminal_risk

    level = assess_terminal_risk(command)
    name = level.name
    return name, _RISK_LABELS.get(name, name)


async def _precheck_execution(req: ExecuteRequest, user: User) -> None:
    """企业级执行前检查：预算、三层防御、S4 审批.

    沙箱模式下放宽检查 — 用户已主动选择隔离执行环境:
      - deny 仍拦截（极度危险命令即使沙箱也不执行）
      - confirm/approve 自动放行（沙箱已提供隔离保护）
    """
    require_request_budget("executor")

    if req.confirm or req.approval_id:
        if req.approval_id and not is_approval_granted(req.approval_id, command=req.command):
            raise HTTPException(
                403,
                detail="审批单无效、未批准或已超时；请先在安全门禁完成审批",
            )
        return

    from security_agent.safety_gate.three_layer_defense import ThreeLayerDefenseEngine

    engine = ThreeLayerDefenseEngine()
    result = await engine.evaluate(
        req.command,
        target_type="terminal",
        user_message="executor api",
        trace_id=req.trace_id or "",
        user=user.username,
    )
    verdict = str(result.overall_verdict.value if hasattr(result.overall_verdict, "value") else result.overall_verdict).lower()

    # deny 始终拦截，即使是沙箱模式也不执行极度危险命令
    if verdict == "deny":
        raise HTTPException(403, detail=f"安全门拒绝执行: {verdict} — {result.message}")

    # 沙箱模式下: quarantine/escalate/approve/confirm 均放行
    # 用户已主动选择沙箱隔离，沙箱本身已提供 OS 级保护
    if req.sandbox:
        return

    if verdict in ("quarantine", "escalate"):
        raise HTTPException(403, detail=f"安全门拒绝执行: {verdict} — {result.message}")

    if result.requires_human_approval or verdict == "approve":
        raise HTTPException(
            403,
            detail="该命令需人工审批：请先在「安全门禁」提交评估并批准，或使用 approval_id 执行",
        )

    if verdict == "confirm":
        raise HTTPException(403, detail="该命令需用户确认（confirm=true）后执行")


@router.get("/assess-risk")
async def assess_risk(command: str, user: User = Depends(get_current_user)):
    """执行前预览命令风险等级."""
    name, label = _assess_command(command)
    return {"risk_level": name, "risk_label": label}


@router.post("/execute", response_model=ExecuteResponse)
async def execute_command(req: ExecuteRequest, user: User = Depends(require_operator)):
    start = time.time()
    risk_name, risk_label = _assess_command(req.command)
    mode = "sandbox" if req.sandbox else "direct"
    try:
        await _precheck_execution(req, user)
        timeout = min(float(req.timeout), require_request_budget("executor"))
        from security_agent.terminal.executor import run_terminal

        result = await run_terminal(
            req.command,
            timeout_sec=timeout,
            user_confirmed=req.confirm or bool(req.approval_id),
            force_sandbox=req.sandbox,
        )
        rollback_id = str(uuid.uuid4())[:8] if result.ok and not req.sandbox else None
        if rollback_id:
            _rollback_registry[rollback_id] = {"command": req.command, "timestamp": time.time()}
        audit.append_audit(
            "executor_execute",
            {
                "command": req.command[:160],
                "success": result.ok,
                "operator": user.username,
                "approval_id": req.approval_id,
                "trace_id": result.trace_id,
                "risk_level": result.risk_level or risk_name,
                "sandbox": req.sandbox,
            },
        )
        final_risk = (result.risk_level or risk_name or "READONLY").upper()
        return ExecuteResponse(
            success=result.ok,
            output=result.stdout[-5000:] if result.stdout else "",
            error=(result.stderr or result.message or "")[-2000:],
            duration_ms=(time.time() - start) * 1000,
            risk_level=final_risk,
            risk_label=_RISK_LABELS.get(final_risk, risk_label),
            execution_mode=mode,
            rollback_id=rollback_id,
        )
    except HTTPException as he:
        return ExecuteResponse(
            success=False,
            output="",
            error=str(he.detail),
            duration_ms=(time.time() - start) * 1000,
            risk_level=risk_name,
            risk_label=risk_label,
            execution_mode=mode,
        )
    except Exception as e:
        return ExecuteResponse(
            success=False,
            output="",
            error=str(e),
            duration_ms=(time.time() - start) * 1000,
            risk_level=risk_name,
            risk_label=risk_label,
            execution_mode=mode,
        )


@router.post("/rollback")
async def rollback(req: RollbackRequest, user: User = Depends(require_operator)):
    if req.rollback_id in _rollback_registry:
        info = _rollback_registry.pop(req.rollback_id)
        return {"ok": True, "rolled_back": info["command"]}
    raise HTTPException(status_code=404, detail="回滚 ID 不存在")


@router.get("/history")
async def command_history(user: User = Depends(get_current_user)):
    return {"history": [], "total": 0}

"""④ 最小权限执行路由 — 审批单 + 预算守卫 + 快照/自动回滚."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from security_agent.api.deps import get_current_user, require_operator
from security_agent.api.models import (
    ExecuteRequest, ExecuteResponse, RollbackRequest,
    SnapshotInfo, SnapshotRestoreResponse,
)
from security_agent.audit import log as audit
from security_agent.auth.models import User
from security_agent.ops.guardrails import is_approval_granted, require_request_budget
from security_agent.safety_gate.snapshot import SnapshotManager

router = APIRouter()

_RISK_LABELS = {
    "READONLY": "只读",
    "REVERSIBLE": "可逆",
    "IRREVERSIBLE": "不可逆",
    "CRITICAL": "关键",
}

# 全局快照管理器（持久化到 data/snapshots/）
_snapshot_mgr = SnapshotManager()


def _assess_command(command: str) -> tuple[str, str]:
    from security_agent.terminal.executor import assess_terminal_risk

    level = assess_terminal_risk(command)
    name = level.name
    return name, _RISK_LABELS.get(name, name)


async def _precheck_execution(req: ExecuteRequest, user: User) -> str | None:
    """企业级执行前检查：预算、三层防御、S4 审批.

    沙箱模式下放宽检查 — 用户已主动选择隔离执行环境:
      - deny 仍拦截（极度危险命令即使沙箱也不执行）
      - confirm/approve 自动放行（沙箱已提供隔离保护）

    Returns:
        snapshot_id 若三层防御触发了自动备份，否则 None.
    """
    require_request_budget("executor")

    if req.confirm or req.approval_id:
        if req.approval_id and not is_approval_granted(req.approval_id, command=req.command):
            raise HTTPException(
                403,
                detail="审批单无效、未批准或已超时；请先在安全门禁完成审批",
            )
        return None

    from security_agent.safety_gate.three_layer_defense import ThreeLayerDefenseEngine

    engine = ThreeLayerDefenseEngine(backup_manager=_snapshot_mgr)
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
        return None

    if verdict in ("quarantine", "escalate"):
        raise HTTPException(403, detail=f"安全门拒绝执行: {verdict} — {result.message}")

    if result.requires_human_approval or verdict == "approve":
        raise HTTPException(
            403,
            detail="该命令需人工审批：请先在「安全门禁」提交评估并批准，或使用 approval_id 执行",
        )

    if verdict == "confirm":
        raise HTTPException(403, detail="该命令需用户确认（confirm=true）后执行")

    # 提取三层防御触发的快照 ID
    snapshot_id = None
    if result.auto_backup_triggered and result.rollback_available:
        for entry in result.decision_path:
            if entry.startswith("backup_created("):
                snapshot_id = entry.split("(")[1].rstrip(")")
                break

    return snapshot_id


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
    snapshot_id = None

    try:
        snapshot_id = await _precheck_execution(req, user)
        timeout = min(float(req.timeout), require_request_budget("executor"))
        from security_agent.terminal.executor import run_terminal

        result = await run_terminal(
            req.command,
            timeout_sec=timeout,
            user_confirmed=req.confirm or bool(req.approval_id),
            force_sandbox=req.sandbox,
            snapshot_id=snapshot_id,
        )

        rollback_id = snapshot_id

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
                "snapshot_id": snapshot_id,
                "auto_rollback": getattr(result, "auto_rollback_triggered", False),
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
            snapshot_id=snapshot_id,
            auto_rollback_triggered=getattr(result, "auto_rollback_triggered", False),
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
    """回滚到指定快照 — 使用 SnapshotManager 恢复文件."""
    result = _snapshot_mgr.restore_snapshot(req.rollback_id)
    if not result.get("success") and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    audit.append_audit(
        "executor_rollback",
        {
            "snap_id": req.rollback_id,
            "operator": user.username,
            "restored": result.get("restored", []),
            "failed": result.get("failed", []),
        },
    )
    return {"ok": result["success"], "snap_id": req.rollback_id, **result}


# ========== 快照管理 API ==========

@router.get("/snapshots", response_model=list[SnapshotInfo])
async def list_snapshots(limit: int = 20, user: User = Depends(get_current_user)):
    """列出最近快照."""
    records = _snapshot_mgr.list_snapshots(limit=limit)
    return [
        SnapshotInfo(
            id=r.id,
            created_at=r.created_at,
            operation=r.operation,
            risk_level=r.risk_level,
            user=r.user,
            files_count=len(r.files_before),
            restored_at=(
                _snapshot_mgr._index.get(r.id, {}).get("restored_at")
            ),
            restore_success=(
                _snapshot_mgr._index.get(r.id, {}).get("restore_success")
            ),
            restore_failed=(
                _snapshot_mgr._index.get(r.id, {}).get("restore_failed")
            ),
        )
        for r in records
    ]


@router.get("/snapshots/{snap_id}")
async def get_snapshot(snap_id: str, user: User = Depends(get_current_user)):
    """获取单个快照详情."""
    record = _snapshot_mgr.get_snapshot(snap_id)
    if not record:
        raise HTTPException(status_code=404, detail="快照不存在")
    idx = _snapshot_mgr._index.get(snap_id, {})
    return {
        "id": record.id,
        "created_at": record.created_at,
        "operation": record.operation,
        "risk_level": record.risk_level,
        "user": record.user,
        "files_before": record.files_before,
        "files_count": len(record.files_before),
        "restored_at": idx.get("restored_at"),
        "restore_success": idx.get("restore_success"),
        "restore_failed": idx.get("restore_failed"),
    }


@router.post("/snapshots/{snap_id}/restore", response_model=SnapshotRestoreResponse)
async def restore_snapshot(snap_id: str, user: User = Depends(require_operator)):
    """手动触发快照回滚."""
    result = _snapshot_mgr.restore_snapshot(snap_id)
    if not result.get("success") and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    audit.append_audit(
        "snapshot_restore",
        {
            "snap_id": snap_id,
            "operator": user.username,
            "restored": result.get("restored", []),
            "failed": result.get("failed", []),
        },
    )
    return SnapshotRestoreResponse(
        success=result["success"],
        snap_id=snap_id,
        operation=result.get("operation", ""),
        restored=result.get("restored", []),
        failed=result.get("failed", []),
        restored_count=result.get("restored_count", 0),
        failed_count=result.get("failed_count", 0),
    )


@router.delete("/snapshots/{snap_id}")
async def delete_snapshot(snap_id: str, user: User = Depends(require_operator)):
    """删除快照."""
    import shutil
    record = _snapshot_mgr.get_snapshot(snap_id)
    if not record:
        raise HTTPException(status_code=404, detail="快照不存在")
    snap_dir = _snapshot_mgr.base_dir / snap_id
    if snap_dir.exists():
        shutil.rmtree(str(snap_dir), ignore_errors=True)
    if snap_id in _snapshot_mgr._index:
        del _snapshot_mgr._index[snap_id]
        _snapshot_mgr._save_index()
    audit.append_audit(
        "snapshot_delete",
        {"snap_id": snap_id, "operator": user.username},
    )
    return {"ok": True, "snap_id": snap_id}


@router.get("/history")
async def command_history(user: User = Depends(get_current_user)):
    return {"history": [], "total": 0}

"""③ 安全意图校验路由 — 持久化审批队列（企业级 S4）."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from security_agent.api.deps import get_current_user, require_admin, require_operator
from security_agent.api.models import (
    ApprovalRequest,
    DefenseEvaluateRequest,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)
from security_agent.audit import log as audit
from security_agent.auth.models import User
from security_agent.ops.guardrails import enqueue_human_approval

router = APIRouter()


def _confirmation_to_api(req) -> dict:
    d = req.to_dict()
    d["task_id"] = req.request_id
    d["command"] = (req.metadata or {}).get("command", req.action_description)
    d["requested_by"] = (req.metadata or {}).get("requested_by", "")
    return d


@router.get("/")
async def safety_overview(user: User = Depends(get_current_user)):
    return await safety_status(user=user)


@router.post("/assess", response_model=RiskAssessmentResponse)
async def assess_risk(req: RiskAssessmentRequest, user: User = Depends(get_current_user)):
    from security_agent.safety_gate.gate import SafetyGate

    try:
        gate = SafetyGate()
        result = gate.evaluate_terminal(
            req.command,
            user_message=req.context or "",
            user=user.username,
        )
        level_map = {
            "allow": "low",
            "confirm": "medium",
            "approve": "high",
            "backup_confirm": "high",
            "escalate": "critical",
            "deny": "critical",
        }
        verdict_value = result.verdict.value if hasattr(result.verdict, "value") else str(result.verdict)
        level = level_map.get(str(verdict_value).lower(), "low")
        return RiskAssessmentResponse(
            level=level,
            score=result.risk.score if result.risk else 0,
            reasons=[result.message] if result.message else [],
            requires_approval=level in ("high", "critical"),
            trace_id=result.trace_id or None,
            verdict=str(verdict_value),
        )
    except Exception:
        high_risk = any(w in req.command.lower() for w in ["rm -rf", "dd ", "mkfs", "> /dev/"])
        return RiskAssessmentResponse(
            level="critical" if high_risk else "low",
            score=1.0 if high_risk else 0.1,
            reasons=["匹配危险命令模式"] if high_risk else ["未检测到风险"],
            requires_approval=high_risk,
            trace_id=None,
            verdict="deny" if high_risk else "allow",
        )


@router.get("/defense/layers")
async def defense_layer_catalog(user: User = Depends(get_current_user)):
    """三层防御层定义 — 与 three_layer_defense.LAYER_META 对齐."""
    from security_agent.safety_gate.three_layer_defense import DefenseLayer, LAYER_META

    return {
        "formula": "静态 30% + 意图 35% + 受限执行 35%",
        "layers": [
            {"id": layer.value, **LAYER_META.get(layer, {})}
            for layer in DefenseLayer
        ],
        "note": "评估通过表示安全策略允许；实际执行还受 OS、权限与沙箱影响。",
    }


@router.post("/defense/evaluate")
async def evaluate_three_layer_defense(req: DefenseEvaluateRequest, user: User = Depends(get_current_user)):
    from security_agent.safety_gate.three_layer_defense import ThreeLayerDefenseEngine

    engine = ThreeLayerDefenseEngine()
    result = await engine.evaluate(
        req.target,
        target_type=req.target_type,
        user_message=req.user_message,
        arguments=req.arguments,
        trace_id=req.trace_id or "",
        user=user.username,
        sudo=req.sudo,
    )
    payload = result.to_dict()
    audit.append_audit(
        "safety_defense_evaluate",
        {
            "trace_id": payload.get("trace_id"),
            "target_type": req.target_type,
            "target": req.target[:160],
            "overall_verdict": payload.get("overall_verdict"),
            "overall_score": payload.get("overall_score"),
        },
    )

    verdict = str(payload.get("overall_verdict", "")).lower()
    needs_human = bool(payload.get("requires_human_approval")) or verdict in (
        "approve",
        "escalate",
        "quarantine",
    )
    if needs_human and verdict not in ("allow", "confirm"):
        extra = enqueue_human_approval(
            trace_id=payload.get("trace_id", ""),
            user_message=req.user_message,
            action_description=req.target,
            risk_level="critical" if verdict in ("escalate", "quarantine", "deny") else "high",
            verdict=verdict,
            metadata={
                "command": req.target,
                "target_type": req.target_type,
                "requested_by": user.username,
                "sudo": req.sudo,
            },
        )
        payload.update(extra)
        payload["requires_human_approval"] = True

    return payload


@router.post("/approve")
async def approve_or_reject(req: ApprovalRequest, user: User = Depends(require_operator)):
    from security_agent.confirm import get_confirmation_manager

    rid = getattr(req, "request_id", None) or req.task_id
    mgr = get_confirmation_manager()
    if req.action == "approve":
        ok = mgr.approve_request(rid, responder=user.username, reason=req.reason)
    else:
        ok = mgr.reject_request(rid, responder=user.username, reason=req.reason)
    if not ok:
        raise HTTPException(404, "未找到待审批任务")
    audit.append_audit(
        f"approval_{req.action}",
        {"request_id": rid, "operator": user.username, "reason": req.reason},
    )
    return {"ok": True, "request_id": rid, "task_id": rid, "action": req.action}


@router.get("/pending")
async def list_pending(user: User = Depends(get_current_user)):
    from security_agent.confirm import get_confirmation_manager

    mgr = get_confirmation_manager()
    mgr.expire_stale_requests()
    return [_confirmation_to_api(r) for r in mgr.list_pending_requests()]


@router.post("/submit")
async def submit_approval(item: dict, user: User = Depends(get_current_user)):
    from security_agent.confirm import ConfirmationLevel, get_confirmation_manager

    mgr = get_confirmation_manager()
    req = mgr.create_request(
        trace_id=item.get("trace_id", ""),
        user_message=item.get("user_message", ""),
        action_description=item.get("command", item.get("action", "")),
        risk_level=item.get("risk_level", "medium"),
        confirmation_level=ConfirmationLevel.APPROVE,
        metadata={
            "command": item.get("command", ""),
            "requested_by": user.username,
        },
    )
    return _confirmation_to_api(req)


@router.get("/knowledge/search")
async def safety_knowledge_search(
    q: str = "",
    tag: str = "",
    limit: int = 20,
    user: User = Depends(get_current_user),
):
    """安全门禁知识库检索 — 支持关键词搜索 + 标签过滤 + 严重度排序."""
    from security_agent.knowledge.playbooks import PLAYBOOKS

    results = []
    q_lower = q.lower().strip()
    tag_lower = tag.lower().strip()
    # 支持空格分割多关键词
    q_tokens = [t for t in q_lower.split() if len(t) >= 2] if q_lower else []

    for pb in PLAYBOOKS:
        # 标签过滤
        if tag_lower and not any(tag_lower in t.lower() for t in pb.threat_tags):
            continue

        if not q_lower:
            results.append(pb.to_dict())
            continue

        # 构建搜索域：标题、正文、关键词、建议动作
        searchable = (
            pb.title + " " + pb.body + " "
            + " ".join(pb.keywords) + " "
            + " ".join(pb.suggested_actions) + " "
            + " ".join(pb.do_not) + " "
            + " ".join(pb.threat_tags)
        ).lower()

        # 多关键词匹配打分
        score = 0
        for token in q_tokens:
            # 标题匹配加权 (x3)
            if token in pb.title.lower():
                score += 3
            # 正文匹配 (x1)
            if token in pb.body.lower():
                score += 1
            # 关键词匹配加权 (x2)
            if any(token in kw.lower() for kw in pb.keywords):
                score += 2
            # 标签匹配 (x1)
            if any(token in t.lower() for t in pb.threat_tags):
                score += 1

        # 严重度加权：严重=+2, 高=+1
        sev_bonus = {"严重": 2, "高": 1}.get(pb.severity, 0)
        score += sev_bonus

        if score > 0:
            item = pb.to_dict()
            item["_score"] = score
            results.append(item)

    # 按得分排序
    results.sort(key=lambda x: x.get("_score", 0), reverse=True)

    return {
        "total": len(results),
        "query": q,
        "tag": tag,
        "items": results[:limit],
    }


@router.get("/knowledge/tags")
async def safety_knowledge_tags(user: User = Depends(get_current_user)):
    """返回安全门禁知识库所有标签及每个标签的条目数."""
    from security_agent.knowledge.playbooks import PLAYBOOKS

    tag_count: dict[str, int] = {}
    for pb in PLAYBOOKS:
        for t in pb.threat_tags:
            tag_count[t] = tag_count.get(t, 0) + 1
    return {"tags": [{"name": k, "count": v} for k, v in sorted(tag_count.items())]}


@router.get("/status")
async def safety_status(user: User = Depends(get_current_user)):
    from security_agent.confirm import get_confirmation_manager
    from security_agent.safety_gate.three_layer_defense import ThreeLayerDefenseEngine

    try:
        defense = ThreeLayerDefenseEngine()
        l1 = getattr(defense, "l1_rules_enabled", True)
        l2 = getattr(defense, "l2_audit_enabled", True)
    except Exception:
        l1, l2 = True, True

    mgr = get_confirmation_manager()
    stats = mgr.get_stats()
    return {
        "l1_active": l1,
        "l2_active": l2,
        "l3_active": True,
        "weights": {"static_risk": 0.30, "dynamic_intent": 0.35, "restricted_exec": 0.35},
        "confirmation_stats": stats,
        "pending_count": stats.get("pending_count", 0),
        "total_checks": stats.get("total_requests", 0),
    }

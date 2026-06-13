"""L1 分析计划与 L3 执行 — 持久化计划仓 + 三感知 + 阶段锁 + 全链路 trace."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from security_agent.pipeline.trace_id import normalize_trace_id
from security_agent.storage.plan_store import get_plan_store

# 进程内缓存（与 SQLite 双写，加速热路径）
_PLANS: dict[str, dict[str, Any]] = {}


def _persist(plan: dict[str, Any]) -> None:
    _PLANS[plan["plan_id"]] = plan
    get_plan_store().save(plan)


def get_plan(plan_id: str) -> Optional[dict[str, Any]]:
    if plan_id in _PLANS:
        return _PLANS[plan_id]
    loaded = get_plan_store().get(plan_id)
    if loaded:
        _PLANS[plan_id] = loaded
    return loaded


async def build_analysis_plan(
    message: str,
    *,
    batch_id: Optional[str] = None,
) -> dict[str, Any]:
    from security_agent.agent.l1_triple_perception import run_triple_perception_parallel
    from security_agent.agent.orchestrator import build_plan
    from security_agent.pipeline.coordination import record_l1_analyze

    plan_id = uuid.uuid4().hex[:12]
    trace_id = normalize_trace_id(uuid.uuid4().hex[:12])
    core = build_plan(message)

    htn_path: dict[str, Any] = {}
    tool_chain = list(core.get("tool_chain") or [])
    if tool_chain and not core.get("skill_flow"):
        from security_agent.pipeline.htn_planner import optimize_tool_chain

        htn_path = optimize_tool_chain(tool_chain, core.get("intent", "general"))
        tool_chain = htn_path.get("chain") or tool_chain

    sandbox_envelope = None
    if tool_chain:
        try:
            from security_agent.pipeline.sandbox_gate import sandbox_preview

            for tool_name in tool_chain:
                preview = sandbox_preview(tool_name, core.get("tool_args", {}).get(tool_name, {}))
                if preview.get("sandbox_required"):
                    sandbox_envelope = preview
                    break
        except Exception:
            pass

    triple = await run_triple_perception_parallel(message)
    boundary_block = triple["adversarial_boundary"]
    knowledge_block = triple["sensitive_knowledge"]
    static_block = triple["static_environment_eye"]

    boundary_hits = boundary_block.get("hits") or []
    knowledge_refs = knowledge_block.get("refs") or []
    static_snapshot = static_block.get("snapshot") or {}

    requires_confirm = any(
        h.get("verdict") in ("NEED_CONFIRM", "DENY", "QUARANTINE") for h in boundary_hits
    ) or bool(boundary_block.get("privilege_escalation_probes"))

    steps = [
        {"id": "tp1", "layer": "L1", "title": "抗性边界感知", "status": "done"},
        {"id": "tp2", "layer": "L1", "title": "灵敏知识库检索", "status": "done"},
        {"id": "tp3", "layer": "L1", "title": "静态环境感知（眼）", "status": "done"},
        {"id": "i", "layer": "L1", "title": "意图识别", "status": "done"},
        {"id": "g", "layer": "L2", "title": "安全防护沙箱", "status": "pending"},
        {"id": "x", "layer": "L3", "title": "推理分发 execute", "status": "pending"},
    ]

    plan: dict[str, Any] = {
        "plan_id": plan_id,
        "trace_id": trace_id,
        "batch_id": batch_id,
        "intent": core.get("intent", "general"),
        "message": message,
        "user_message_resolved": core.get("user_message_resolved") or message,
        "tool_chain": tool_chain,
        "tool_chain_raw": core.get("tool_chain") or [],
        "htn_path": htn_path or None,
        "sandbox_envelope": sandbox_envelope,
        "tool_args": core.get("tool_args") or {},
        "skill_flow": core.get("skill_flow"),
        "use_llm_tools": bool(core.get("use_llm_tools")),
        "hint": core.get("hint") or "",
        "phase": "analyze",
        "phase_lock": "L1_only",
        "steps": steps,
        "triple_perception": triple,
        "boundary_hits": boundary_hits,
        "knowledge_refs": knowledge_refs,
        "static_snapshot": static_snapshot,
        "requires_confirm": requires_confirm,
        "l2_verdict": None,
        "status": "planned",
    }
    record_l1_analyze(plan)
    _persist(plan)
    return plan


async def run_l2_precheck(plan_id: str) -> dict[str, Any]:
    plan = get_plan(plan_id)
    if not plan:
        raise KeyError(plan_id)

    verdict = "pass"
    detail: dict[str, Any] = {}

    for hit in plan.get("boundary_hits") or []:
        v = hit.get("verdict", "ALLOW")
        if v == "DENY":
            verdict = "deny"
            break
        if v in ("NEED_CONFIRM", "QUARANTINE"):
            verdict = "confirm"

    tp = plan.get("triple_perception") or {}
    pe_probes = (tp.get("adversarial_boundary") or {}).get("privilege_escalation_probes") or []
    if pe_probes and verdict == "pass":
        verdict = "confirm"
        detail["privilege_escalation_probes"] = pe_probes

    cmd = None
    for hit in plan.get("boundary_hits") or []:
        if hit.get("input"):
            cmd = hit["input"]
            break

    if cmd and verdict != "deny":
        try:
            from security_agent.safety_gate.three_layer_defense import ThreeLayerDefenseEngine
            engine = ThreeLayerDefenseEngine()
            ev = engine.evaluate(
                target=cmd,
                target_type="terminal",
                user_message=plan.get("message") or "",
            )
            detail = ev.to_dict() if hasattr(ev, "to_dict") else {"verdict": getattr(ev, "verdict", "allow")}
            ev_v = str(detail.get("verdict") or detail.get("final_verdict") or "allow").lower()
            if "deny" in ev_v:
                verdict = "deny"
            elif "confirm" in ev_v or "quarantine" in ev_v:
                verdict = "confirm" if verdict != "deny" else verdict
        except Exception as e:
            detail = {"error": str(e)}

    plan["l2_verdict"] = verdict
    plan["l2_detail"] = detail
    for s in plan.get("steps") or []:
        if s.get("layer") == "L2":
            s["status"] = "done" if verdict == "pass" else ("blocked" if verdict == "deny" else "confirm")
    plan["status"] = "l2_pass" if verdict == "pass" else ("l2_blocked" if verdict == "deny" else "l2_confirm")

    result = {"verdict": verdict, "detail": detail, "plan_id": plan_id}
    from security_agent.pipeline.coordination import record_l2_precheck
    record_l2_precheck(plan, result)
    _persist(plan)
    return result


async def execute_plan(
    plan_id: str,
    *,
    session_id: Optional[str] = None,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    plan = get_plan(plan_id)
    if not plan:
        raise KeyError(plan_id)

    if plan.get("l2_verdict") is None:
        await run_l2_precheck(plan_id)
        plan = get_plan(plan_id) or plan

    verdict = plan.get("l2_verdict")
    if verdict == "deny":
        raise ValueError("L2 安全管控拒绝执行")

    needs_confirm = bool(plan.get("requires_confirm")) or verdict == "confirm"
    if needs_confirm and not user_confirmed:
        raise ValueError("需要用户确认后再执行")

    from security_agent.pipeline.coordination import record_gate_pass, record_l3_execute_start
    from security_agent.agent.core_agents import core_dispatch_agent, audit_iteration_agent

    record_gate_pass(plan)
    record_l3_execute_start(plan)
    tid = normalize_trace_id(session_id or plan.get("trace_id"))

    payload = await core_dispatch_agent.execute_phase(
        plan,
        session_id=tid,
        user_confirmed=user_confirmed,
        trace_id=tid,
    )
    payload["trace_id"] = normalize_trace_id(payload.get("trace_id") or tid)

    audit_summary = await audit_iteration_agent.finalize(
        plan,
        execute_result=payload,
        l2_result={"verdict": plan.get("l2_verdict")},
    )
    payload["audit"] = audit_summary

    for s in plan.get("steps") or []:
        if s.get("layer") == "L3":
            s["status"] = "done"
    plan["status"] = "executed"
    plan["phase"] = "execute"
    plan["execute_result"] = payload
    _persist(plan)
    return payload

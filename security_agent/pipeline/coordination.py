"""流水线协调 — L1/L2/L3 阶段写入统一 trace 卷宗."""

from __future__ import annotations

from typing import Any

from security_agent.audit import log as audit
from security_agent.pipeline.trace_id import normalize_trace_id
from security_agent.storage.trace_storage import TraceStorage


def _storage() -> TraceStorage:
    return TraceStorage()


def record_l1_analyze(plan: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(plan.get("trace_id"))
    plan["trace_id"] = trace_id
    store = _storage()
    store.create_trace(
        trace_id,
        user_message=(plan.get("message") or "")[:500],
        metadata={
            "plan_id": plan.get("plan_id"),
            "batch_id": plan.get("batch_id"),
            "phase": "analyze",
            "intent": plan.get("intent"),
        },
    )
    tp = plan.get("triple_perception") or {}
    store.add_stage(trace_id, "L1_triple_perception", {
        "modules": ["adversarial_boundary", "sensitive_knowledge", "static_environment_eye"],
        "boundary_hits": len(plan.get("boundary_hits") or []),
        "knowledge_refs": len(plan.get("knowledge_refs") or []),
        "privilege_probes": len(
            (tp.get("adversarial_boundary") or {}).get("privilege_escalation_probes") or []
        ),
    })
    store.add_stage(trace_id, "L1_intent", {"intent": plan.get("intent")})
    audit.append_audit("pipeline_L1_analyze", {"trace_id": trace_id, "plan_id": plan.get("plan_id")})


def record_l2_precheck(plan: dict[str, Any], l2: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(plan.get("trace_id"))
    _storage().add_stage(trace_id, "L2_safety_sandbox", {
        "verdict": l2.get("verdict"),
        "detail_keys": list((l2.get("detail") or {}).keys())[:10],
    })
    audit.append_audit("pipeline_L2_precheck", {"trace_id": trace_id, "verdict": l2.get("verdict")})


def record_l3_execute_start(plan: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(plan.get("trace_id"))
    _storage().add_stage(trace_id, "L3_execute_start", {
        "plan_id": plan.get("plan_id"),
        "tool_chain": plan.get("tool_chain") or [],
        "skill_flow": plan.get("skill_flow"),
    })


def record_l4_finalize(plan: dict[str, Any], audit_summary: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(audit_summary.get("trace_id") or plan.get("trace_id"))
    _storage().add_stage(trace_id, "L4_audit_finalize", audit_summary)
    _storage().complete_trace(trace_id, status="completed")
    audit.append_audit("pipeline_L4_finalize", {"trace_id": trace_id, "plan_id": plan.get("plan_id")})

"""流水线协调 — L1/L2/GATE/L3/L4/L5 阶段写入统一 trace 卷宗."""

from __future__ import annotations

from typing import Any

from security_agent.audit import log as audit
from security_agent.pipeline.stage_meta import enrich_stage_data
from security_agent.pipeline.trace_id import normalize_trace_id
from security_agent.storage.trace_storage import TraceStorage


def _storage() -> TraceStorage:
    return TraceStorage()


def _add_stage(trace_id: str, stage_name: str, data: dict[str, Any] | None = None) -> None:
    _storage().add_stage(trace_id, stage_name, enrich_stage_data(stage_name, data))


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
    htn = plan.get("htn_path") or {}
    _add_stage(trace_id, "L1_triple_perception", {
        "layer": "L1",
        "tool": "triple_perception",
        "modules": ["adversarial_boundary", "sensitive_knowledge", "static_environment_eye"],
        "boundary_hits": len(plan.get("boundary_hits") or []),
        "knowledge_refs": len(plan.get("knowledge_refs") or []),
        "privilege_probes": len(
            (tp.get("adversarial_boundary") or {}).get("privilege_escalation_probes") or []
        ),
    })
    _add_stage(trace_id, "L1_intent", {
        "layer": "L1",
        "tool": "intent_detect",
        "intent": plan.get("intent"),
        "path_id": htn.get("path_id"),
        "htn_steps": htn.get("htn_steps") or [],
    })
    audit.append_audit("pipeline_L1_analyze", {"trace_id": trace_id, "plan_id": plan.get("plan_id")})


def record_l2_precheck(plan: dict[str, Any], l2: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(plan.get("trace_id"))
    _add_stage(trace_id, "L2_safety_sandbox", {
        "layer": "L2",
        "tool": "sandbox_precheck",
        "cluster": "repair",
        "verdict": l2.get("verdict"),
        "detail_keys": list((l2.get("detail") or {}).keys())[:10],
    })
    audit.append_audit("pipeline_L2_precheck", {"trace_id": trace_id, "verdict": l2.get("verdict")})


def record_gate_pass(plan: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(plan.get("trace_id"))
    _add_stage(trace_id, "GATE_layer_pass", {
        "layer": "GATE",
        "tool": "layer_gate",
        "l2_verdict": plan.get("l2_verdict"),
        "plan_id": plan.get("plan_id"),
        "mode": "L2_pass_to_L3",
    })


def record_l3_execute_start(plan: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(plan.get("trace_id"))
    _add_stage(trace_id, "L3_execute_start", {
        "layer": "L3",
        "plan_id": plan.get("plan_id"),
        "tool_chain": plan.get("tool_chain") or [],
        "skill_flow": plan.get("skill_flow"),
        "path_id": (plan.get("htn_path") or {}).get("path_id"),
    })


def record_l4_finalize(plan: dict[str, Any], audit_summary: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(audit_summary.get("trace_id") or plan.get("trace_id"))
    _add_stage(trace_id, "L4_audit_finalize", {
        "layer": "L4",
        "tool": "audit_finalize",
        **audit_summary,
    })
    _storage().complete_trace(trace_id, status="completed")
    audit.append_audit("pipeline_L4_finalize", {"trace_id": trace_id, "plan_id": plan.get("plan_id")})


def record_l5_analytics(plan: dict[str, Any], audit_summary: dict[str, Any]) -> None:
    trace_id = normalize_trace_id(audit_summary.get("trace_id") or plan.get("trace_id"))
    tools = audit_summary.get("tools_invoked") or 0
    _add_stage(trace_id, "L5_analytics_snapshot", {
        "layer": "L5",
        "tool": "l5_metrics",
        "tools_invoked": tools,
        "intent": plan.get("intent"),
        "l2_verdict": audit_summary.get("l2_verdict"),
        "metrics_snapshot": audit_summary.get("metrics_snapshot") or {},
    })
    audit.append_audit("pipeline_L5_analytics", {"trace_id": trace_id, "tools": tools})

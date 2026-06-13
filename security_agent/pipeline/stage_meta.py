"""Structured layer / tool / cluster metadata for trace stages."""

from __future__ import annotations

from typing import Any

from security_agent.pipeline.tool_taxonomy import classify_tool

_PREFIX_LAYER = (
    ("L1_", "L1"),
    ("L2_", "L2"),
    ("GATE_", "GATE"),
    ("L3_", "L3"),
    ("L4_", "L4"),
    ("L5_", "L5"),
)

_BRAIN_STAGE_LAYER: dict[str, str] = {
    "receive_request": "L1",
    "environment_probe": "L1",
    "environment_probe_result": "L3",
    "inference_decision": "L3",
    "safety_check": "L2",
    "execution": "L3",
    "skill_flow_start": "L3",
    "skill_flow_end": "L3",
    "approved_plan_dispatch": "GATE",
    "harness_verify": "L2",
    "post_verify": "L4",
}


def _infer_layer(stage_name: str) -> str:
    for prefix, layer in _PREFIX_LAYER:
        if stage_name.startswith(prefix):
            return layer
    return _BRAIN_STAGE_LAYER.get(stage_name, "L3")


def _infer_tool(stage_name: str, payload: dict[str, Any]) -> str | None:
    for key in ("tool", "tool_name", "command"):
        val = payload.get(key)
        if val:
            return str(val)
    if stage_name == "L3_execute_start":
        chain = payload.get("tool_chain") or []
        if chain:
            return str(chain[0])
    return None


def enrich_stage_data(stage_name: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge authoritative layer/tool/cluster fields into stage payload."""
    payload = dict(data or {})
    payload.setdefault("layer", _infer_layer(stage_name))
    tool = _infer_tool(stage_name, payload)
    if tool:
        payload.setdefault("tool", tool)
        payload.setdefault("cluster", classify_tool(tool))
    if stage_name == "L3_execute_start":
        chain = payload.get("tool_chain") or []
        if chain:
            payload.setdefault(
                "clusters",
                [classify_tool(str(t)) for t in chain],
            )
    payload["stage_key"] = stage_name
    return payload

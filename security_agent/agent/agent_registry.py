"""三智能体注册表 — 从 data/contracts/triple_unify.json 加载（三方统一真源）."""

from __future__ import annotations

from typing import Any

from security_agent.contracts.loader import agents_with_defaults, get_contract

_c = get_contract()

AGENT_REGISTRY: list[dict[str, Any]] = agents_with_defaults()

TOOL_CLUSTERS: list[dict[str, Any]] = list(_c.get("tool_clusters") or [])

ORCHESTRATOR: dict[str, Any] = {
    **(_c.get("orchestrator") or {}),
    "formula": _c.get("formula", ""),
}

PIPELINE_LAYERS: list[str] = list(_c.get("main_line") or [])

PIPELINE_LAYER_DETAIL: list[dict[str, Any]] = list(_c.get("pipeline_layers") or [])

LAYER_AGENT_MAP: dict[str, str] = dict(_c.get("layer_agent_map") or {})


def default_agent_stages() -> list[dict[str, Any]]:
    return [
        {
            "agent": a["agent"],
            "display_name": a["display_name"],
            "layer": a["layer"],
            "status": "idle",
            "detail": "",
        }
        for a in AGENT_REGISTRY
    ]

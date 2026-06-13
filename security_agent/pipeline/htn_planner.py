"""0-1 cost HTN-style tool path planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from security_agent.pipeline.tool_taxonomy import cluster_order_key, summarize_chain, tool_cost

_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "data" / "mcp" / "workflow_manifest.json"


def _load_manifest() -> dict[str, Any]:
    if not _MANIFEST_PATH.is_file():
        return {"workflows": []}
    try:
        return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"workflows": []}


def _match_workflow(intent: str, chain: list[str]) -> dict[str, Any] | None:
    manifest = _load_manifest()
    tools_set = set(chain)
    best: dict[str, Any] | None = None
    best_score = -1
    for wf in manifest.get("workflows") or []:
        if not isinstance(wf, dict):
            continue
        if wf.get("intent") and wf["intent"] != intent:
            continue
        wf_tools = set(wf.get("tool_chain") or [])
        if not wf_tools:
            continue
        overlap = len(tools_set & wf_tools)
        if overlap > best_score:
            best_score = overlap
            best = wf
    return best


def optimize_tool_chain(
    chain: list[str],
    intent: str = "general",
    *,
    max_cost: int | None = None,
) -> dict[str, Any]:
    if not chain:
        return {
            "chain": [],
            "intent": intent,
            "total_cost": 0,
            "path_id": None,
            "method": "htn_0_1_cost",
            "clusters": {},
            "skipped": [],
        }

    seen: set[str] = set()
    deduped: list[str] = []
    for name in chain:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)

    ordered = sorted(deduped, key=lambda t: (cluster_order_key(t), tool_cost(t), t))
    skipped: list[str] = []
    if max_cost is not None:
        trimmed: list[str] = []
        acc = 0
        for name in ordered:
            c = tool_cost(name)
            if acc + c > max_cost and c > 0:
                skipped.append(name)
                continue
            acc += c
            trimmed.append(name)
        ordered = trimmed

    summary = summarize_chain(ordered)
    wf = _match_workflow(intent, ordered)
    path_id = (wf or {}).get("id")
    htn_steps = (wf or {}).get("htn_steps") or [
        {"task": "gather", "cluster": "metrics"},
        {"task": "correlate", "cluster": "logs"},
        {"task": "remediate", "cluster": "repair"},
        {"task": "orchestrate", "cluster": "dispatch"},
    ]

    return {
        "chain": ordered,
        "intent": intent,
        "total_cost": summary["total_cost"],
        "read_only_cost": summary["read_only_cost"],
        "clusters": summary["clusters"],
        "path_id": path_id,
        "workflow_title": (wf or {}).get("title"),
        "htn_steps": htn_steps,
        "method": "htn_0_1_cost",
        "reference": "LangGraph-style decomposition; workflow_manifest",
        "skipped": skipped,
    }

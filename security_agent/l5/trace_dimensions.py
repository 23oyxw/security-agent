"""L5 six-dimension scores from shared L4 trace stage data."""

from __future__ import annotations

import json
from typing import Any

from security_agent.agent.evaluation import PRIOR, _bayes_shrink

REPAIR_INTENTS = frozenset({
    "scan", "scan_report", "alert_response", "block", "full_check",
    "processes", "repair", "secure_exec_flow",
})
DISPATCH_INTENTS = frozenset({
    "autonomous", "monitor_status", "monitor_start", "monitor_stop",
    "parallel_info", "health", "audit", "report",
})
REPAIR_CLUSTERS = frozenset({"repair", "metrics"})
DISPATCH_CLUSTERS = frozenset({"dispatch", "info"})


def _parse_stage_data(stage: dict[str, Any]) -> dict[str, Any]:
    data = stage.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}
    return data if isinstance(data, dict) else {}


def _stage_failed(data: dict[str, Any]) -> bool:
    verdict = str(data.get("verdict") or "").lower()
    if verdict in ("fail", "deny", "error", "failed"):
        return True
    return bool(data.get("error"))


def _trace_success(trace: dict[str, Any]) -> bool:
    if trace.get("failed"):
        return False
    status = str(trace.get("status") or "").lower()
    if status in ("failed", "error", "cancelled"):
        return False
    if status in ("completed", "success", "done") or "complete" in status:
        return True
    return not trace.get("failed", False)


def _enrich_trace_stats(trace_row: dict[str, Any], full: dict[str, Any]) -> dict[str, Any]:
    stats = {
        "l3_tool_calls": 0,
        "l3_tool_hits": 0,
        "repair_steps": 0,
        "repair_ok": 0,
        "dispatch_steps": 0,
        "dispatch_ok": 0,
        "knowledge_steps": 0,
        "pipeline_steps": 0,
        "pipeline_ok": 0,
    }
    for stage in full.get("stages") or []:
        data = _parse_stage_data(stage)
        layer = str(data.get("layer") or "").upper()
        cluster = str(data.get("cluster") or "")
        tool = data.get("tool")
        failed = _stage_failed(data)

        if layer == "L1" and tool in ("triple_perception", "intent_detect", "knowledge_retrieval"):
            stats["knowledge_steps"] += 1
        elif layer == "L1" and (data.get("citations") or data.get("intent")):
            stats["knowledge_steps"] += 1

        if cluster in REPAIR_CLUSTERS or (layer == "L3" and cluster in REPAIR_CLUSTERS):
            stats["repair_steps"] += 1
            if not failed:
                stats["repair_ok"] += 1

        if cluster in DISPATCH_CLUSTERS or layer == "GATE":
            stats["dispatch_steps"] += 1
            if not failed:
                stats["dispatch_ok"] += 1

        if layer == "L3" and tool:
            stats["l3_tool_calls"] += 1
            if not failed:
                stats["l3_tool_hits"] += 1

        if layer in ("L3", "L4", "L5") and tool:
            stats["pipeline_steps"] += 1
            if not failed:
                stats["pipeline_ok"] += 1

    return stats


def compute_trace_dimension_raw(traces: list[dict[str, Any]], enriched: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    n = len(traces)
    if n == 0:
        return {}

    out: dict[str, dict[str, Any]] = {}

    intent_hits = sum(
        1 for t, e in zip(traces, enriched)
        if t.get("intent_key") not in (None, "", "general") or e["knowledge_steps"] > 0
    )
    out["knowledge_relevance"] = {"raw": intent_hits / n, "sample_count": n, "source": "trace"}

    repair_idx = [
        i for i, (t, e) in enumerate(zip(traces, enriched))
        if t.get("intent_key") in REPAIR_INTENTS or e["repair_steps"] > 0
    ]
    if repair_idx:
        ok = sum(1 for i in repair_idx if _trace_success(traces[i]))
        out["success_rate"] = {"raw": ok / len(repair_idx), "sample_count": len(repair_idx), "source": "trace_repair"}
    else:
        ok = sum(1 for t in traces if _trace_success(t))
        out["success_rate"] = {"raw": ok / n, "sample_count": n, "source": "trace"}

    dispatch_idx = [
        i for i, (t, e) in enumerate(zip(traces, enriched))
        if t.get("intent_key") in DISPATCH_INTENTS or e["dispatch_steps"] > 0
    ]
    if dispatch_idx:
        util_vals = []
        for i in dispatch_idx:
            e = enriched[i]
            if e["dispatch_steps"] > 0:
                util_vals.append(e["dispatch_ok"] / e["dispatch_steps"])
            elif _trace_success(traces[i]):
                util_vals.append(1.0)
            else:
                util_vals.append(0.0)
        out["efficiency_ratio"] = {
            "raw": sum(util_vals) / len(util_vals),
            "sample_count": len(dispatch_idx),
            "source": "trace_dispatch",
        }
    else:
        ratios = []
        for t in traces:
            stages = int(t.get("stage_count") or 0)
            if stages >= 2 and _trace_success(t):
                dur = max(float(t.get("duration_ms") or 0), 1.0)
                stage_ms = float(t.get("stage_ms") or 0)
                ratios.append(min(1.0, stage_ms / dur if dur else 0.7))
        out["efficiency_ratio"] = {
            "raw": sum(ratios) / max(len(ratios), 1) if ratios else sum(1 for t in traces if _trace_success(t)) / n,
            "sample_count": len(ratios) or n,
            "source": "trace",
        }

    total_calls = sum(e["l3_tool_calls"] for e in enriched)
    total_hits = sum(e["l3_tool_hits"] for e in enriched)
    if total_calls > 0:
        out["step_efficiency"] = {
            "raw": total_hits / total_calls,
            "sample_count": total_calls,
            "source": "trace_l3_tools",
        }
    else:
        tool_traces = [i for i, e in enumerate(enriched) if e["repair_steps"] + e["dispatch_steps"] > 0]
        if tool_traces:
            ok = sum(1 for i in tool_traces if enriched[i]["repair_ok"] + enriched[i]["dispatch_ok"] > 0)
            out["step_efficiency"] = {"raw": ok / len(tool_traces), "sample_count": len(tool_traces), "source": "trace_cluster"}
        else:
            out["step_efficiency"] = {"raw": sum(1 for t in traces if _trace_success(t)) / n, "sample_count": n, "source": "trace"}

    pipeline_steps = sum(e["pipeline_steps"] for e in enriched)
    if pipeline_steps >= 2:
        pipeline_ok = sum(e["pipeline_ok"] for e in enriched)
        out["stability"] = {"raw": pipeline_ok / pipeline_steps, "sample_count": pipeline_steps, "source": "trace_pipeline"}
    else:
        batch_traces = [t for t in traces if int(t.get("stage_count") or 0) >= 2]
        if batch_traces:
            ok = sum(1 for t in batch_traces if _trace_success(t))
            out["stability"] = {"raw": ok / len(batch_traces), "sample_count": len(batch_traces), "source": "trace_batch"}
        else:
            out["stability"] = {"raw": sum(1 for t in traces if _trace_success(t)) / n, "sample_count": n, "source": "trace"}

    ok_boundary = sum(1 for t in traces if _trace_success(t))
    out["safety_compliance"] = {"raw": ok_boundary / n, "sample_count": n, "source": "trace_status"}

    return out


def load_enriched_traces(limit: int = 50) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from security_agent.storage.trace_catalog import load_shared_traces
    from security_agent.storage.trace_storage import get_trace_storage

    traces = load_shared_traces(limit=limit)
    storage = get_trace_storage()
    enriched = [_enrich_trace_stats(t, storage.get_trace(t.get("trace_id", "")) or {}) for t in traces]
    return traces, enriched


def merge_trace_dimensions_into_l5(
    raw: dict[str, float],
    shrunk: dict[str, float],
    confidence: dict[str, float],
    *,
    trace_limit: int = 50,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, Any]]:
    traces, enriched = load_enriched_traces(limit=trace_limit)
    trace_raw = compute_trace_dimension_raw(traces, enriched)
    meta: dict[str, Any] = {"trace_count": len(traces), "sources": {}}

    raw_out = dict(raw)
    shrunk_out = dict(shrunk)
    conf_out = dict(confidence)

    for eval_key, td in trace_raw.items():
        n = int(td.get("sample_count") or 0)
        if n < 1:
            continue
        obs = float(td["raw"])
        raw_out[eval_key] = round(obs, 4)
        post, conf = _bayes_shrink(obs, n, PRIOR.get(eval_key, 0.75))
        eval_shrunk = shrunk_out.get(eval_key)
        if eval_shrunk is not None and shrunk:
            weight = min(1.0, n / 8.0)
            blended = post * weight + float(eval_shrunk) * (1.0 - weight)
            shrunk_out[eval_key] = round(blended, 4)
            conf_out[eval_key] = round(max(conf, confidence.get(eval_key, 0)), 4)
        else:
            shrunk_out[eval_key] = post
            conf_out[eval_key] = conf
        meta["sources"][eval_key] = td.get("source", "trace")

    return raw_out, shrunk_out, conf_out, meta
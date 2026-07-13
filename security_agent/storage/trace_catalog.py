"""L4/L5 共享 Trace 目录 — 统一列表过滤与指标口径."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from security_agent.storage.trace_storage import get_trace_storage


def embedded_sub_trace_ids(scan_limit: int = 120) -> set[str]:
    """skill_flow_end 内嵌子 trace，列表与 L5 聚合时排除."""
    sub_ids: set[str] = set()
    try:
        storage = get_trace_storage()
        for row in storage.list_traces(limit=scan_limit):
            full = storage.get_trace(row.get("trace_id", "")) or {}
            for stage in full.get("stages") or []:
                data = stage.get("data")
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        data = {}
                if not isinstance(data, dict):
                    continue
                inner = str(data.get("trace_id") or "").strip()
                outer = str(full.get("trace_id") or "").strip()
                if inner and inner != outer:
                    sub_ids.add(inner)
                    if not inner.startswith("trace-") and len(inner) >= 8:
                        sub_ids.add(f"trace-{inner[:12]}")
    except Exception:
        pass
    return sub_ids


def _trace_row_for_analytics(row: dict[str, Any], *, stage_count: int = 0, stage_ms: float = 0) -> dict[str, Any]:
    from security_agent.agent.orchestrator import detect_intent
    from security_agent.l5.analytics import _normalize_duration_ms, _normalize_error_rate

    wall_ms = 0.0
    if row.get("created_at") and row.get("completed_at"):
        try:
            c = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
            d = datetime.fromisoformat(str(row["completed_at"]).replace("Z", "+00:00"))
            wall_ms = max(0.0, (d - c).total_seconds() * 1000)
        except ValueError:
            pass
    stages_n = stage_count or int(row.get("stage_count") or 0)
    user_msg = row.get("user_message") or ""
    intent_key = detect_intent(user_msg) if user_msg else "general"
    trace_row: dict[str, Any] = {
        "trace_id": row["trace_id"],
        "duration_ms": wall_ms or float(stage_ms or 0),
        "stage_ms": float(stage_ms or 0),
        "stages": stages_n,
        "stage_count": stages_n,
        "failed": row.get("status") == "failed",
        "status": row.get("status"),
        "timestamp": row.get("created_at"),
        "intent": user_msg[:48],
        "user_message": user_msg,
        "intent_key": intent_key,
        "path_id": intent_key,
        "service": intent_key,
        "error_rate": 100.0 if row.get("status") == "failed" else 0.0,
        "metadata": row.get("metadata"),
        "created_at": row.get("created_at"),
        "completed_at": row.get("completed_at"),
    }
    stages_payload = row.get("stages") if isinstance(row.get("stages"), list) else None
    trace_row["duration_ms"] = _normalize_duration_ms(trace_row, stages_payload or [])
    trace_row["error_rate"] = _normalize_error_rate(trace_row, stages_payload or [])
    return trace_row


def load_shared_traces(limit: int = 200, *, exclude_sub_traces: bool = True) -> list[dict[str, Any]]:
    """L4 列表与 L5 图表共用：含 stage_count / 耗时 / 意图."""
    storage = get_trace_storage()
    sub_ids = embedded_sub_trace_ids() if exclude_sub_traces else set()
    rows = storage.list_traces_summary(limit=max(limit * 2, limit))
    out: list[dict[str, Any]] = []
    for row in rows:
        tid = row.get("trace_id", "")
        if not tid or (exclude_sub_traces and tid in sub_ids):
            continue
        out.append(_trace_row_for_analytics(
            row,
            stage_count=int(row.get("stage_count") or 0),
            stage_ms=float(row.get("stage_ms") or 0),
        ))
        if len(out) >= limit:
            break
    return out
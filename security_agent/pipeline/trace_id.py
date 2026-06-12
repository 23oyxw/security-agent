"""全链路 trace_id 规范化 — L1 analyze 与 L3 execute 共用."""

from __future__ import annotations

import uuid

from security_agent.audit.spine import new_trace_id


def normalize_trace_id(trace_id: str | None) -> str:
    if not trace_id or not str(trace_id).strip():
        return new_trace_id()
    tid = str(trace_id).strip()
    if tid.startswith("trace-"):
        return tid
    return f"trace-{tid.replace('trace-', '')[:12]}"

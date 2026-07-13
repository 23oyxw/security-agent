"""Compact trace memo for chat + side panel (no LLM)."""

from __future__ import annotations

from typing import Any


def build_execute_memo(
    *,
    trace_id: str,
    plan: dict[str, Any] | None = None,
    tool_trace: list[dict[str, Any]] | None = None,
    audit: dict[str, Any] | None = None,
    max_lines: int = 24,
) -> str:
    """Build a short trace minutes block for inline display."""
    plan = plan or {}
    tools = []
    for entry in tool_trace or []:
        if isinstance(entry, dict) and entry.get("tool"):
            tools.append(str(entry["tool"]))

    lines = [
        "## Trace 执行纪要",
        f"- **Trace** `{trace_id or '—'}`",
        f"- **Plan** `{str(plan.get('plan_id', '—'))[:12]}`",
        f"- **意图** {plan.get('intent', '—')}",
        f"- **L2** {plan.get('l2_verdict') or audit and audit.get('l2_verdict') or '—'}",
    ]
    if tools:
        lines.append(f"- **工具** {' → '.join(dict.fromkeys(tools))}")
    if audit:
        lines.append(
            f"- **L4 审计** 工具 {audit.get('tools_invoked', 0)} 次 · "
            f"状态 {audit.get('audit_status', 'recorded')}"
        )

    bundle_memo = _memo_from_bundle(trace_id)
    if bundle_memo:
        lines.append("")
        lines.extend(bundle_memo.splitlines()[: max(0, max_lines - len(lines))])

    lines.append("")
    lines.append(f"_完整链路图：侧边 Trace 面板或 `/trace?id={trace_id}`_")
    return "\n".join(lines)


def _memo_from_bundle(trace_id: str) -> str:
    if not trace_id:
        return ""
    try:
        from security_agent.audit.spine import export_incident_bundle
        from security_agent.audit.trace_report import bundle_to_text

        bundle = export_incident_bundle(trace_id)
        if not bundle.get("sqlite_trace") and not bundle.get("reasoning_report"):
            return ""
        text = bundle_to_text(bundle)
        # Keep headline + timeline snippet only
        out: list[str] = []
        for line in text.splitlines():
            if not line.strip():
                if out and out[-1] != "":
                    out.append("")
                continue
            out.append(line)
            if len(out) >= 14:
                out.append("…")
                break
        return "\n".join(out)
    except Exception:
        return ""


def build_memo_payload(trace_id: str) -> dict[str, Any]:
    """API payload: memo text + chart nodes for frontend."""
    nodes: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    try:
        from security_agent.visualizer.trace_visualizer import get_trace_visualizer

        viz = get_trace_visualizer().get_trace_visualization(trace_id)
        if viz:
            d = viz.to_dict()
            nodes = d.get("nodes") or []
            summary = d.get("summary") or {}
    except Exception:
        pass

    if not nodes:
        try:
            from security_agent.storage.trace_storage import get_trace_storage
            from security_agent.timeutil import format_storage_timestamp

            row = get_trace_storage().get_trace(trace_id) or {}
            for i, s in enumerate(row.get("stages") or []):
                nodes.append({
                    "name": s.get("name", f"stage-{i}"),
                    "duration_ms": int(s.get("duration_ms") or 0),
                    "timestamp": format_storage_timestamp(s.get("timestamp", "")),
                    "layer": (s.get("data") or {}).get("layer") if isinstance(s.get("data"), dict) else None,
                })
            summary = {
                "status": row.get("status"),
                "user_message": (row.get("user_message") or "")[:200],
            }
        except Exception:
            pass

    memo = _memo_from_bundle(trace_id) or f"Trace `{trace_id}` 已记录，暂无详细纪要。"
    chart = []
    for n in nodes[:20]:
        label = n.get("name") or n.get("stage_key") or "stage"
        chart.append({
            "label": str(label)[:24],
            "duration_ms": int(n.get("duration_ms") or 0),
            "layer": n.get("layer"),
        })

    return {
        "trace_id": trace_id,
        "memo": memo,
        "summary": summary,
        "chart": chart,
        "nodes_count": len(nodes),
    }

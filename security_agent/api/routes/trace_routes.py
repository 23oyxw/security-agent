"""⑤ 推理链路溯源路由 — 事件脊柱导出."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from security_agent.api.deps import get_current_user
from security_agent.api.models import TraceVisualization
from security_agent.auth.models import User

router = APIRouter()


class TraceCleanupRequest(BaseModel):
    trace_ids: list[str] | None = None  # None = 清理所有超过 days 的
    days: int = 30


@router.post("/cleanup")
async def cleanup_traces(body: TraceCleanupRequest = TraceCleanupRequest(), user: User = Depends(get_current_user)):
    """批量清理 Trace。传 trace_ids 删除指定；不传则清理 days 天前的旧记录"""
    from security_agent.storage.trace_storage import get_trace_storage

    storage = get_trace_storage()
    deleted = 0

    if body.trace_ids:
        for tid in body.trace_ids:
            try:
                storage.delete_trace(tid)
                deleted += 1
            except Exception:
                pass
    else:
        try:
            deleted = storage.cleanup_old_traces(days=body.days)
        except Exception:
            deleted = 0

    return {"ok": True, "deleted_count": deleted, "acknowledged_by": user.username}


@router.get("/stats")
async def trace_stats(user: User = Depends(get_current_user)):
    """Trace 统计"""
    from security_agent.storage.trace_storage import get_trace_storage

    try:
        storage = get_trace_storage()
        all_traces = storage.list_traces(limit=500)
        total = len(all_traces)
        by_status: dict[str, int] = {}
        degradation: dict[str, int] = {}
        for t in all_traces:
            st = str(t.get("status", "unknown"))
            by_status[st] = by_status.get(st, 0) + 1
            dl = str((t.get("metadata") or {}).get("degradation_level", "S0"))
            degradation[dl] = degradation.get(dl, 0) + 1
        return {
            "total": total,
            "by_status": by_status,
            "by_degradation": degradation,
        }
    except Exception:
        return {"total": 0, "by_status": {}, "by_degradation": {}}


@router.get("/heatmap")
async def trace_heatmap(days: int = 7, user: User = Depends(get_current_user)):
    """Trace 时段热力 — 按日×小时聚合真实 trace 创建时间."""
    from collections import defaultdict
    from datetime import datetime, timedelta

    from security_agent.storage.trace_storage import get_trace_storage
    from security_agent.timeutil import parse_iso

    days = max(1, min(days, 14))
    now = datetime.now()
    day_keys: list[str] = []
    for i in range(days - 1, -1, -1):
        day_keys.append((now - timedelta(days=i)).strftime("%Y-%m-%d"))

    grid: dict[str, list[int]] = {d: [0] * 24 for d in day_keys}
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    try:
        storage = get_trace_storage()
        for row in storage.list_traces(limit=500):
            raw = row.get("created_at") or ""
            dt = parse_iso(str(raw))
            if not dt:
                continue
            if hasattr(dt, "tzinfo") and dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            day = dt.strftime("%Y-%m-%d")
            if day not in grid:
                continue
            grid[day][dt.hour] += 1
    except Exception:
        pass

    data: list[list[int]] = []
    day_labels: list[str] = []
    for d in day_keys:
        dt = datetime.strptime(d, "%Y-%m-%d")
        day_labels.append(f"{labels[dt.weekday()]} {d[5:]}")
        data.append(grid[d])

    flat = []
    max_val = 0
    for yi, row in enumerate(data):
        for xi, val in enumerate(row):
            flat.append([xi, yi, val])
            max_val = max(max_val, val)

    return {
        "days": days,
        "hours": list(range(24)),
        "day_labels": day_labels,
        "data": flat,
        "max": max_val,
        "total": sum(sum(r) for r in data),
        "source": "trace_storage",
    }


@router.get("/{trace_id}", response_model=TraceVisualization)
async def get_trace(trace_id: str, user: User = Depends(get_current_user)):
    """获取推理链路可视化."""
    try:
        from security_agent.visualizer.trace_visualizer import get_trace_visualizer

        viz = get_trace_visualizer().get_trace_visualization(trace_id)
        if viz:
            d = viz.to_dict()
            return TraceVisualization(
                trace_id=d["trace_id"],
                nodes=d.get("nodes", []),
                links=d.get("links", []),
                summary=d.get("summary", {}),
            )
    except Exception:
        pass

    try:
        from security_agent.audit.trace_report import _stage_duration_deltas
        from security_agent.storage.trace_storage import get_trace_storage
        from security_agent.timeutil import format_storage_timestamp

        row = get_trace_storage().get_trace(trace_id)
        if row:
            stages = row.get("stages") or []
            deltas = _stage_duration_deltas(stages)
            nodes = [
                {
                    "node_id": f"stage-{i}",
                    "name": s.get("name", ""),
                    "stage_key": (s.get("data") or {}).get("stage_key") or s.get("name", ""),
                    "type": "stage",
                    "timestamp": format_storage_timestamp(s.get("timestamp", "")),
                    "duration_ms": deltas[i] if i < len(deltas) else s.get("duration_ms", 0),
                    "status": "success",
                    "details": s.get("data") or {},
                    "layer": (s.get("data") or {}).get("layer"),
                    "tool": (s.get("data") or {}).get("tool"),
                    "cluster": (s.get("data") or {}).get("cluster"),
                }
                for i, s in enumerate(row.get("stages", []))
            ]
            return TraceVisualization(
                trace_id=trace_id,
                nodes=nodes,
                links=[],
                summary={
                    "status": row.get("status"),
                    "user_message": (row.get("user_message") or "")[:200],
                    "degradation_level": (row.get("metadata") or {}).get("degradation_level"),
                },
            )
    except Exception:
        pass

    return TraceVisualization(
        trace_id=trace_id,
        nodes=[],
        links=[],
        summary={"status": "not_found", "message": "链路未找到"},
    )


@router.get("/{trace_id}/export")
async def export_trace(
    trace_id: str,
    format: str = Query("text", alias="format", pattern="^(text|html|json)$"),
    user: User = Depends(get_current_user),
):
    """导出 Trace：text=执行纪要(txt)，html=matplotlib 可视化分析；json=调试."""
    from security_agent.audit.spine import export_incident_bundle
    from security_agent.audit.trace_report import bundle_to_html, bundle_to_text

    bundle = export_incident_bundle(trace_id)
    if not bundle.get("sqlite_trace") and not bundle.get("reasoning_report"):
        raise HTTPException(404, f"trace not found: {trace_id}")

    if format == "json":
        return JSONResponse(content=bundle)

    if format == "html":
        content = bundle_to_html(bundle)
        media = "text/html; charset=utf-8"
        filename = f"{trace_id}-analysis.html"
    else:
        content = bundle_to_text(bundle)
        media = "text/plain; charset=utf-8"
        filename = f"{trace_id}-minutes.txt"

    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _trace_ts_key(item: dict) -> str:
    from security_agent.timeutil import parse_iso

    raw = item.get("timestamp_raw") or item.get("timestamp") or ""
    dt = parse_iso(raw)
    return dt.isoformat() if dt else ""


def _embedded_sub_trace_ids(scan_limit: int = 120) -> set[str]:
    """skill_flow_end 里引用的短 trace_id，列表中不再单独展示."""
    import json

    from security_agent.storage.trace_storage import get_trace_storage

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


@router.get("/")
async def list_traces(limit: int = 20, user: User = Depends(get_current_user)):
    """列出最近推理链路."""
    from security_agent.timeutil import format_display, now_iso, parse_iso

    traces: list[dict] = []
    seen: set[str] = set()
    sub_trace_ids = _embedded_sub_trace_ids()

    try:
        from security_agent.storage.trace_storage import get_trace_storage

        for row in get_trace_storage().list_traces(limit=limit * 2):
            tid = row.get("trace_id", "")
            if not tid or tid in seen or tid in sub_trace_ids:
                continue
            seen.add(tid)
            status = str(row.get("status", "unknown"))
            meta = row.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            raw_ts = row.get("created_at", "") or ""
            traces.append({
                "trace_id": tid,
                "timestamp": format_display(raw_ts) if raw_ts else format_display(now_iso()),
                "timestamp_raw": raw_ts,
                "action": (row.get("user_message") or "")[:120],
                "target": (row.get("user_message") or "")[:80],
                "reasoning": status,
                "status": "success" if status.startswith("completed") else status,
                "risk_score": 0.0,
                "outcome": status,
                "degradation_level": (meta or {}).get("degradation_level"),
            })
    except Exception:
        pass

    if len(traces) < limit:
        try:
            from security_agent import config
            from security_agent.audit.reasoning_trace import ReasoningTrace

            trace_dir = config.DATA_DIR / "traces"
            if trace_dir.is_dir():
                for fp in sorted(trace_dir.glob("*.jsonl"), reverse=True):
                    for rec in ReasoningTrace.from_jsonl(fp):
                        tid = rec.get("trace_id", "")
                        if not tid or tid in seen:
                            continue
                        seen.add(tid)
                        summary = rec.get("safety_summary") or {}
                        raw_ts = rec.get("finished_at") or rec.get("created_at", "")
                        traces.append({
                            "trace_id": tid,
                            "timestamp": format_display(raw_ts) if raw_ts else "—",
                            "timestamp_raw": raw_ts,
                            "action": (rec.get("user_message") or "")[:120],
                            "target": (rec.get("user_message") or "")[:80],
                            "reasoning": rec.get("strategy", ""),
                            "status": "success" if rec.get("status") == "completed" else rec.get("status", "unknown"),
                            "risk_score": (summary.get("avg_safety_score") or 100) / 100.0,
                            "outcome": rec.get("status", "unknown"),
                            "degradation_level": rec.get("metadata", {}).get("degradation_level"),
                        })
                        if len(traces) >= limit:
                            break
                    if len(traces) >= limit:
                        break
        except Exception:
            pass

    traces.sort(key=_trace_ts_key, reverse=True)
    return {"traces": traces[:limit], "total": len(traces[:limit])}

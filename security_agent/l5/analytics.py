"""L5 链路可视化分析 — 3σ/IQR 离群 + 热力矩阵."""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any


def _sigma_outliers(values: list[float], threshold: float = 3.0) -> set[int]:
    if len(values) < 3:
        return set()
    mu = statistics.mean(values)
    try:
        sd = statistics.stdev(values)
    except statistics.StatisticsError:
        return set()
    if sd <= 0:
        return set()
    return {i for i, v in enumerate(values) if abs(v - mu) > threshold * sd}


def _iqr_outliers(values: list[float], k: float = 1.5) -> set[int]:
    if len(values) < 4:
        return set()
    qs = statistics.quantiles(values, n=4)
    q1, q3 = qs[0], qs[2]
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return {i for i, v in enumerate(values) if v < lo or v > hi}


def build_scatter_from_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """每条 trace 一个散点：耗时 × 错误率 × 抖动."""
    points: list[dict[str, Any]] = []
    latencies: list[float] = []
    for t in traces:
        dur = float(t.get("duration_ms") or t.get("total_ms") or 0)
        stages = int(t.get("stages") or t.get("stage_count") or 0)
        failed = bool(t.get("failed") or t.get("status") == "failed")
        jitter = float(t.get("jitter_ms") or max(0, dur * 0.05))
        err = 100.0 if failed else float(t.get("error_rate") or 0)
        latencies.append(dur)
        points.append({
            "trace_id": t.get("trace_id") or t.get("id"),
            "path_id": t.get("path_id") or t.get("intent") or "unknown",
            "latency_ms": round(dur, 1),
            "error_rate": round(err, 2),
            "jitter_ms": round(jitter, 1),
            "stages": stages,
            "service": t.get("service") or t.get("intent") or "agent",
        })

    sigma_idx = _sigma_outliers(latencies)
    iqr_idx = _iqr_outliers(latencies)
    for i, p in enumerate(points):
        p["outlier_sigma"] = i in sigma_idx
        p["outlier_iqr"] = i in iqr_idx
        p["is_anomaly"] = p["outlier_sigma"] or p["outlier_iqr"] or p["error_rate"] >= 50

    return {
        "model": "3σ + IQR",
        "definition": "以 trace 为散点：X=耗时(ms) Y=错误率(%) 大小=抖动；3σ/IQR 标红离群",
        "points": points,
        "anomaly_count": sum(1 for p in points if p["is_anomaly"]),
    }


def build_heatmap_from_traces(traces: list[dict[str, Any]], *, bucket_hours: int = 4) -> dict[str, Any]:
    """时间 × 服务接口 二维热度."""
    if not traces:
        return {"model": "weighted_density", "x_labels": [], "y_labels": [], "matrix": [], "definition": ""}

    services = sorted({str(t.get("service") or t.get("intent") or "agent") for t in traces})
    buckets: dict[str, dict[str, float]] = {}

    for t in traces:
        ts = t.get("started_at") or t.get("timestamp") or t.get("created_at")
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
        elif isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now()
        else:
            dt = datetime.now()
        bucket = f"{dt.hour // bucket_hours * bucket_hours:02d}-{(dt.hour // bucket_hours * bucket_hours + bucket_hours) % 24:02d}h"
        svc = str(t.get("service") or t.get("intent") or "agent")
        dur = float(t.get("duration_ms") or 0)
        failed = 1.0 if t.get("failed") or t.get("status") == "failed" else 0.0
        risk = min(100.0, dur / 50.0 + failed * 40.0)
        buckets.setdefault(bucket, {})
        buckets[bucket][svc] = buckets[bucket].get(svc, 0.0) + risk

    x_labels = sorted(buckets.keys())
    matrix = [[round(buckets[b].get(s, 0.0), 1) for s in services] for b in x_labels]

    return {
        "model": "weighted_density",
        "definition": "时间桶×服务接口；热度=耗时权重+失败加权，识别成片/时段/集群异常",
        "x_labels": x_labels,
        "y_labels": services,
        "matrix": matrix,
    }


def build_root_cause(trace_detail: dict[str, Any] | None) -> dict[str, Any]:
    """从 trace stage 拆解根因候选."""
    if not trace_detail:
        return {"steps": [], "root_cause": "无 trace 数据", "spans": []}

    stages = trace_detail.get("stages") or trace_detail.get("events") or []
    spans = []
    max_dur = 0.0
    slowest = None
    error_node = None

    for s in stages:
        name = s.get("stage") or s.get("name") or s.get("layer") or "?"
        dur = float(s.get("duration_ms") or s.get("elapsed_ms") or 0)
        err = s.get("error") or s.get("status") == "failed"
        spans.append({"name": name, "duration_ms": dur, "error": bool(err)})
        if dur > max_dur:
            max_dur = dur
            slowest = name
        if err and not error_node:
            error_node = name

    root = error_node or slowest or "unknown"
    hints = {
        "database": "慢 SQL / 连接池",
        "middleware": "中间件阻塞",
        "gateway": "网关超时",
        "L3": "工具/MCP 执行异常",
        "L2": "安全闸门拦截",
    }
    hint = next((v for k, v in hints.items() if k.lower() in str(root).lower()), "链路节点异常")

    return {
        "trace_id": trace_detail.get("trace_id"),
        "spans": spans,
        "slowest": slowest,
        "error_node": error_node,
        "root_cause": hint,
        "steps": [
            "可视化异常点位",
            "提取 Trace/Span 标识",
            "逐级拆解调用链",
            "对比正常基线",
            f"锁定根因：{hint}",
        ],
    }

"""L5 链路可视化分析 — 3σ/IQR 离群 + 热力矩阵."""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from typing import Any

# 固定 4 小时时间桶（按自然顺序，避免字符串排序错乱）
HEATMAP_BUCKETS: list[tuple[int, int]] = [
    (0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24),
]

INTENT_DISPLAY: dict[str, str] = {
    "health": "健康巡检",
    "scan": "安全扫描",
    "scan_report": "扫描报告",
    "processes": "进程排查",
    "repair": "故障修复",
    "monitor_status": "监控状态",
    "parallel_info": "并行采集",
    "general": "通用对话",
    "block": "拦截处置",
    "autonomous": "自主任务",
    "terminal": "终端命令",
    "audit": "审计日志",
}


def _parse_ts(ts: Any) -> datetime:
    if isinstance(ts, (int, float)):
        sec = ts / 1000 if ts > 1e12 else ts
        return datetime.fromtimestamp(sec)
    if isinstance(ts, str) and ts.strip():
        raw = ts.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(raw[:19], fmt)
                except ValueError:
                    continue
    return datetime.now()


def _bucket_key(hour: int, bucket_hours: int = 4) -> str:
    start = (hour // bucket_hours) * bucket_hours
    end = min(start + bucket_hours, 24)
    return f"{start:02d}-{end:02d}"


def _bucket_index(hour: int, bucket_hours: int = 4) -> int:
    return min(len(HEATMAP_BUCKETS) - 1, hour // bucket_hours)


def _intent_key(trace: dict[str, Any]) -> str:
    key = str(trace.get("intent_key") or trace.get("path_id") or "").strip()
    if key and key in INTENT_DISPLAY:
        return key
    if key and len(key) <= 24 and " " not in key:
        return key
    try:
        from security_agent.agent.orchestrator import detect_intent

        msg = str(trace.get("intent") or trace.get("user_message") or "")
        return detect_intent(msg) if msg else "general"
    except Exception:
        return "general"


def _intent_label(key: str) -> str:
    return INTENT_DISPLAY.get(key, key or "general")


def _stage_error_ratio(stages: list[dict[str, Any]]) -> float:
    if not stages:
        return 0.0
    err = 0
    for s in stages:
        data = s.get("data") or s.get("stage_data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}
        if not isinstance(data, dict):
            data = {}
        if s.get("error") or data.get("error") or data.get("ok") is False:
            err += 1
    return err / len(stages)


def _normalize_duration_ms(trace: dict[str, Any], stages: list[dict[str, Any]] | None = None) -> float:
    stage_ms = float(trace.get("stage_ms") or 0)
    if not stage_ms and stages:
        stage_ms = sum(float(s.get("duration_ms") or 0) for s in stages)
    wall_ms = float(trace.get("duration_ms") or trace.get("total_ms") or 0)
    n_stages = int(trace.get("stages") or trace.get("stage_count") or len(stages or []) or 0)

    if stage_ms > 0 and wall_ms > max(stage_ms * 4, 600_000):
        dur = stage_ms
    elif stage_ms > 0 and wall_ms > 0:
        dur = max(stage_ms, min(wall_ms, 300_000))
    else:
        dur = stage_ms or wall_ms or max(n_stages * 180, 200)

    return round(min(max(dur, 50.0), 300_000.0), 1)


def _normalize_error_rate(trace: dict[str, Any], stages: list[dict[str, Any]] | None = None) -> float:
    status = str(trace.get("status") or "").lower()
    failed = bool(trace.get("failed")) or status in ("failed", "error")
    stage_ratio = _stage_error_ratio(stages or [])
    dur = _normalize_duration_ms(trace, stages)
    slow_bonus = min(22.0, dur / 500.0)

    if failed:
        score = 18.0 + stage_ratio * 45.0 + slow_bonus
    else:
        score = 4.0 + stage_ratio * 28.0 + slow_bonus * 0.4

    return round(min(96.0, max(2.0, score)), 1)


def _risk_score(latency_ms: float, error_rate: float, latencies: list[float]) -> float:
    """0–100 连续风险分：耗时排位 + 阶段异常，避免散点挤在 0/100 两端."""
    if not latencies:
        lat_p = 50.0
    else:
        lo, hi = min(latencies), max(latencies)
        if hi <= lo:
            lat_p = 50.0
        else:
            lat_p = (latency_ms - lo) / (hi - lo) * 100.0
    return round(min(98.0, max(4.0, lat_p * 0.55 + error_rate * 0.45)), 1)


STAGE_LABELS: dict[str, tuple[str, str]] = {
    "receive_request": ("L1", "接收请求"),
    "approved_plan_dispatch": ("GATE", "编排放行"),
    "environment_probe": ("L3", "环境感知"),
    "environment_probe_result": ("L3", "工具执行"),
    "inference_decision": ("L3", "推理决策"),
    "safety_check": ("L2", "安全预检"),
    "harness_verify": ("L2", "护栏校验"),
    "execution": ("L3", "执行分发"),
    "skill_flow_start": ("L3", "Skill 流程"),
    "skill_flow_end": ("L3", "流程结束"),
    "post_verify": ("L4", "审计收尾"),
    "L1_analyze": ("L1", "L1 分析"),
    "L2_safety": ("L2", "L2 安全"),
    "L3_execute": ("L3", "L3 执行"),
    "L4_audit": ("L4", "L4 审计"),
    "L5_metrics": ("L5", "L5 量化"),
}


def _stage_span(stage: dict[str, Any]) -> dict[str, Any]:
    from security_agent.pipeline.stage_meta import _infer_layer

    name = str(stage.get("stage") or stage.get("name") or "?")
    data = stage.get("data") or stage.get("stage_data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}
    if not isinstance(data, dict):
        data = {}

    layer, title = STAGE_LABELS.get(name, (_infer_layer(name), name.replace("_", " ")))
    tools = data.get("tool_chain") or []
    tool = data.get("tool") or data.get("tool_name") or ""
    if tools and not tool:
        tool = ", ".join(str(t) for t in tools[:3])
    dur = float(stage.get("duration_ms") or stage.get("elapsed_ms") or 0)
    err = bool(stage.get("error") or data.get("error") or data.get("ok") is False)

    label = title
    if tool:
        label = f"{title} · {tool}"

    return {
        "name": name,
        "layer": layer,
        "title": title,
        "label": label,
        "tool": tool,
        "duration_ms": round(dur, 1),
        "error": err,
    }


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
    """每条 trace 一个散点：耗时 × 阶段错误率 × 阶段数."""
    points: list[dict[str, Any]] = []
    latencies: list[float] = []
    for t in traces:
        intent_key = _intent_key(t)
        dur = _normalize_duration_ms(t)
        stages = int(t.get("stages") or t.get("stage_count") or 0)
        err = _normalize_error_rate(t)
        jitter = float(t.get("jitter_ms") or max(30.0, dur * 0.04))
        latencies.append(dur)
        points.append({
            "trace_id": t.get("trace_id") or t.get("id"),
            "path_id": intent_key,
            "path_label": _intent_label(intent_key),
            "latency_ms": dur,
            "error_rate": err,
            "jitter_ms": round(jitter, 1),
            "stages": stages,
            "service": intent_key,
        })

    for p in points:
        p["risk_score"] = _risk_score(p["latency_ms"], p["error_rate"], latencies)

    sigma_idx = _sigma_outliers(latencies)
    iqr_idx = _iqr_outliers(latencies)
    risk_idx = _sigma_outliers([p["risk_score"] for p in points]) if len(points) >= 3 else set()

    for i, p in enumerate(points):
        p["outlier_sigma"] = i in sigma_idx
        p["outlier_iqr"] = i in iqr_idx
        p["is_anomaly"] = (
            p["outlier_sigma"]
            or p["outlier_iqr"]
            or i in risk_idx
            or p["risk_score"] >= 72
        )

    return {
        "model": "3σ + IQR",
        "definition": "横轴=链路耗时 纵轴=综合风险分(0–100，非单纯成败)；红点=离群 Trace，点击查看下方溯源",
        "axis_help": {
            "x": "耗时(ms)：完成一次 L1→L4 链路的时间",
            "y": "综合风险：耗时偏高 + 阶段异常加权，数值连续分布",
            "size": "圆点大小固定；重叠时自动微移",
        },
        "points": points,
        "anomaly_count": sum(1 for p in points if p["is_anomaly"]),
        "latency_range": [min(latencies), max(latencies)] if latencies else [0, 0],
    }


def build_heatmap_from_traces(traces: list[dict[str, Any]], *, bucket_hours: int = 4) -> dict[str, Any]:
    """时段 × 意图类型 二维热度（固定网格，避免单行/乱序）."""
    if not traces:
        return {"model": "weighted_density", "x_labels": [], "y_labels": [], "matrix": [], "definition": ""}

    x_labels = [f"{a:02d}-{b:02d}" for a, b in HEATMAP_BUCKETS]
    intent_keys = sorted({_intent_key(t) for t in traces})
    if len(intent_keys) < 2:
        for fallback in ("health", "general", "scan"):
            if fallback not in intent_keys:
                intent_keys.append(fallback)
            if len(intent_keys) >= 3:
                break
    y_labels = [_intent_label(k) for k in intent_keys]
    key_by_label = {lab: k for k, lab in zip(intent_keys, y_labels)}

    # sum risk + count for averaging
    sums: dict[tuple[int, int], float] = {}
    counts: dict[tuple[int, int], int] = {}

    for t in traces:
        dt = _parse_ts(t.get("started_at") or t.get("timestamp") or t.get("created_at"))
        bi = _bucket_index(dt.hour, bucket_hours)
        ik = _intent_key(t)
        yi = intent_keys.index(ik) if ik in intent_keys else intent_keys.index("general") if "general" in intent_keys else 0
        dur = _normalize_duration_ms(t)
        err = _normalize_error_rate(t)
        risk = min(100.0, dur / 80.0 + err * 0.6)
        key = (bi, yi)
        sums[key] = sums.get(key, 0.0) + risk
        counts[key] = counts.get(key, 0) + 1

    matrix: list[list[float]] = []
    for yi in range(len(intent_keys)):
        row: list[float] = []
        for bi in range(len(x_labels)):
            c = counts.get((bi, yi), 0)
            val = sums.get((bi, yi), 0.0) / c if c else 0.0
            row.append(round(val, 1))
        matrix.append(row)

    hotspots: list[dict[str, Any]] = []
    for yi, row in enumerate(matrix):
        for xi, val in enumerate(row):
            if val > 0:
                hotspots.append({
                    "time": x_labels[xi],
                    "intent": y_labels[yi],
                    "value": val,
                })
    hotspots.sort(key=lambda x: -x["value"])

    return {
        "model": "weighted_density",
        "definition": "横轴=一天6个时段(每格4h) 纵轴=意图类型 颜色=平均风险热度",
        "legend": {
            "x": "横轴：00–04、04–08 … 20–24 时（每格 4 小时）",
            "y": "纵轴：健康巡检 / 安全扫描等意图",
            "color": "颜色越深风险越高（慢链路 + 失败加权）",
            "empty": "浅灰格=该时段无此类任务",
        },
        "x_labels": x_labels,
        "y_labels": y_labels,
        "intent_keys": intent_keys,
        "matrix": matrix,
        "key_by_label": key_by_label,
        "hotspots": hotspots[:8],
        "trace_count": len(traces),
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
        span = _stage_span(s if isinstance(s, dict) else {"name": str(s)})
        spans.append(span)
        dur = span["duration_ms"]
        if dur > max_dur:
            max_dur = dur
            slowest = span["title"]
        if span["error"] and not error_node:
            error_node = span["title"]

    for span in spans:
        span["is_slowest"] = span["title"] == slowest and max_dur > 0
        span["is_error"] = span["error"]

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


def _box_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0, "mean": 0, "std": 0, "n": 0}
    vals = sorted(values)
    n = len(vals)
    mean = statistics.mean(vals)
    try:
        std = statistics.stdev(vals)
    except statistics.StatisticsError:
        std = 0.0
    if n >= 4:
        qs = statistics.quantiles(vals, n=4)
        q1, med, q3 = qs[0], statistics.median(vals), qs[2]
    else:
        q1 = med = q3 = vals[n // 2]
    return {
        "min": round(vals[0], 1),
        "q1": round(q1, 1),
        "median": round(med, 1),
        "q3": round(q3, 1),
        "max": round(vals[-1], 1),
        "mean": round(mean, 1),
        "std": round(std, 1),
        "n": n,
    }


def _histogram(values: list[float], bins: int = 12) -> dict[str, Any]:
    if not values:
        return {"edges": [], "counts": [], "bin_labels": []}
    lo, hi = min(values), max(values)
    if hi <= lo:
        hi = lo + 1.0
    step = (hi - lo) / bins
    edges = [round(lo + i * step, 1) for i in range(bins + 1)]
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / step) if step > 0 else 0)
        counts[idx] += 1
    labels = [f"{edges[i]}-{edges[i+1]}" for i in range(bins)]
    return {"edges": edges, "counts": counts, "bin_labels": labels}


def build_distributions_from_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """耗时/风险分布 — 直方图 + 箱线 + 分意图统计（L5 统计依据）."""
    if not traces:
        return {
            "model": "descriptive_stats",
            "definition": "基于 Trace 样本的耗时与风险分布（直方图+箱线图）",
            "latency_histogram": _histogram([]),
            "risk_histogram": _histogram([]),
            "latency_box": _box_stats([]),
            "risk_box": _box_stats([]),
            "intent_breakdown": [],
            "trace_count": 0,
        }

    latencies: list[float] = []
    risks: list[float] = []
    by_intent: dict[str, dict[str, Any]] = {}

    all_lat = [_normalize_duration_ms(t) for t in traces]
    for t in traces:
        dur = _normalize_duration_ms(t)
        err = _normalize_error_rate(t)
        risk = _risk_score(dur, err, all_lat)
        latencies.append(dur)
        risks.append(risk)
        ik = _intent_key(t)
        bucket = by_intent.setdefault(ik, {"intent": _intent_label(ik), "key": ik, "count": 0, "lat_sum": 0.0, "risk_sum": 0.0})
        bucket["count"] += 1
        bucket["lat_sum"] += dur
        bucket["risk_sum"] += risk

    intent_rows = []
    for b in by_intent.values():
        c = b["count"]
        intent_rows.append({
            "intent": b["intent"],
            "key": b["key"],
            "count": c,
            "avg_latency_ms": round(b["lat_sum"] / c, 1),
            "avg_risk": round(b["risk_sum"] / c, 1),
        })
    intent_rows.sort(key=lambda x: -x["count"])

    sorted_lat = sorted(latencies)
    p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)

    return {
        "model": "descriptive_stats + Tukey boxplot",
        "definition": "耗时直方图(分箱) + Tukey 箱线(Q1/Q3/IQR) + 分意图均值",
        "latency_histogram": _histogram(latencies),
        "risk_histogram": _histogram(risks),
        "latency_box": _box_stats(latencies),
        "risk_box": _box_stats(risks),
        "summary": {
            "trace_count": len(traces),
            "p95_latency_ms": round(sorted_lat[p95_idx], 1) if sorted_lat else 0,
            "mean_latency_ms": round(statistics.mean(latencies), 1),
            "mean_risk": round(statistics.mean(risks), 1),
        },
        "intent_breakdown": intent_rows,
        "trace_count": len(traces),
    }


def _layer_matches_dim(layer: str, source_layer: str) -> bool:
    if not source_layer:
        return False
    if source_layer == "L1-L5":
        return layer in ("L4", "L5")
    if source_layer == layer:
        return True
    if "-" in source_layer:
        parts = [p.strip() for p in source_layer.split("-") if p.strip()]
        return layer in parts
    return source_layer.startswith(layer)


def build_layer_cross_report(
    traces: list[dict[str, Any]],
    *,
    l5_dims_report: dict[str, Any] | None = None,
    trace_details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """L1-L5 各层数据对照：静态元数据 + Trace 阶段统计 + L5 维度得分."""
    from security_agent.l5.scoring_spec import LAYER_CROSS_META

    layer_stats: dict[str, dict[str, Any]] = {}
    trace_ids_seen: set[str] = set()

    details = trace_details or []
    if not details and traces:
        try:
            from security_agent.storage.trace_storage import get_trace_storage

            storage = get_trace_storage()
            for t in traces[:120]:
                tid = t.get("trace_id")
                if not tid or tid in trace_ids_seen:
                    continue
                trace_ids_seen.add(tid)
                detail = storage.get_trace(tid)
                if detail:
                    details.append(detail)
        except Exception:
            pass

    for detail in details:
        tid = detail.get("trace_id") or ""
        for s in detail.get("stages") or detail.get("events") or []:
            span = _stage_span(s if isinstance(s, dict) else {"name": str(s)})
            layer = span["layer"]
            bucket = layer_stats.setdefault(layer, {
                "stage_count": 0,
                "duration_ms": 0.0,
                "error_count": 0,
                "trace_ids": set(),
            })
            bucket["stage_count"] += 1
            bucket["duration_ms"] += span["duration_ms"]
            if span["error"]:
                bucket["error_count"] += 1
            if tid:
                bucket["trace_ids"].add(tid)

    dim_list = (l5_dims_report or {}).get("dimensions") or []
    rows: list[dict[str, Any]] = []
    for meta in LAYER_CROSS_META:
        layer = meta["layer"]
        st = layer_stats.get(layer, {})
        trace_set = st.get("trace_ids") or set()
        related = [
            {"key": d.get("key"), "label": d.get("label"), "score": d.get("score")}
            for d in dim_list
            if _layer_matches_dim(layer, str(d.get("source_layer") or ""))
        ]
        rows.append({
            **meta,
            "trace_stages": int(st.get("stage_count") or 0),
            "trace_count": len(trace_set),
            "total_ms": round(float(st.get("duration_ms") or 0), 1),
            "error_stages": int(st.get("error_count") or 0),
            "l5_metrics": related,
            "l5_metric_text": " · ".join(f"{m['label']} {m['score']}%" for m in related) or "—",
        })

    return {
        "definition": "各层产出数据 → 馈入 L5 指标；数字来自 Trace 卷宗 stages 聚合",
        "trace_sample": len(traces),
        "detail_loaded": len(details),
        "rows": rows,
        "layer_stats": {
            k: {
                "stage_count": v.get("stage_count", 0),
                "duration_ms": round(v.get("duration_ms", 0), 1),
                "error_count": v.get("error_count", 0),
                "trace_count": len(v.get("trace_ids") or []),
            }
            for k, v in layer_stats.items()
        },
    }

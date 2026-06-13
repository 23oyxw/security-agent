"""Lightweight DBSCAN clustering without sklearn (LoongArch friendly)."""

from __future__ import annotations

from typing import Any


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def simple_dbscan_2d(
    points: list[tuple[float, float]],
    *,
    eps: float = 1.5,
    min_pts: int = 2,
) -> list[int]:
    n = len(points)
    if n == 0:
        return []
    eps2 = eps * eps
    labels = [-1] * n
    cluster_id = 0

    def region_neighbors(idx: int) -> list[int]:
        p = points[idx]
        return [j for j in range(n) if _dist2(p, points[j]) <= eps2]

    visited = [False] * n
    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbors = region_neighbors(i)
        if len(neighbors) < min_pts:
            labels[i] = -1
            continue
        labels[i] = cluster_id
        seeds = [j for j in neighbors if j != i]
        while seeds:
            j = seeds.pop()
            if not visited[j]:
                visited[j] = True
                j_neighbors = region_neighbors(j)
                if len(j_neighbors) >= min_pts:
                    for k in j_neighbors:
                        if k not in seeds:
                            seeds.append(k)
            if labels[j] == -1:
                labels[j] = cluster_id
        cluster_id += 1
    return labels


def cluster_boundary_hits(hits: list[dict[str, Any]]) -> dict[str, Any]:
    points: list[tuple[float, float]] = []
    meta: list[dict[str, Any]] = []
    verdict_score = {"ALLOW": 0.2, "NEED_CONFIRM": 0.55, "DENY": 0.9, "QUARANTINE": 0.95}

    for h in hits:
        v = str(h.get("verdict") or "ALLOW").upper()
        reasons = h.get("reasons") or []
        x = verdict_score.get(v, 0.5)
        y = min(1.0, 0.3 + len(reasons) * 0.15)
        points.append((x, y))
        meta.append({
            "input": (h.get("input") or "")[:80],
            "verdict": v,
            "type": h.get("type"),
        })

    if not points:
        return {
            "model": "DBSCAN-2D",
            "definition": "Boundary hit clustering on severity x confidence",
            "points": [],
            "clusters": [],
            "noise_count": 0,
        }

    labels = simple_dbscan_2d(points, eps=0.35, min_pts=2)
    clustered: dict[int, list[dict[str, Any]]] = {}
    noise = 0
    out_points: list[dict[str, Any]] = []
    for i, (pt, label) in enumerate(zip(points, labels)):
        row = {
            "x": round(pt[0], 3),
            "y": round(pt[1], 3),
            "cluster": label,
            "is_noise": label < 0,
            **meta[i],
        }
        out_points.append(row)
        if label < 0:
            noise += 1
        else:
            clustered.setdefault(label, []).append(row)

    cluster_summaries = [
        {
            "cluster_id": cid,
            "size": len(rows),
            "dominant_verdict": max(
                {r["verdict"] for r in rows},
                key=lambda v: sum(1 for r in rows if r["verdict"] == v),
            ),
        }
        for cid, rows in sorted(clustered.items())
    ]

    return {
        "model": "DBSCAN-2D",
        "definition": "L1 boundary clustering: X=verdict severity Y=rule confidence",
        "points": out_points,
        "clusters": cluster_summaries,
        "noise_count": noise,
        "eps": 0.35,
        "min_pts": 2,
    }


def cluster_trace_latencies(traces: list[dict[str, Any]]) -> dict[str, Any]:
    points: list[tuple[float, float]] = []
    meta: list[dict[str, Any]] = []
    for t in traces:
        dur = float(t.get("duration_ms") or 0)
        err = float(t.get("error_rate") or (100.0 if t.get("failed") else 0.0))
        points.append((dur / 1000.0, err / 100.0))
        meta.append({
            "trace_id": t.get("trace_id"),
            "intent": t.get("intent"),
            "service": t.get("service"),
        })

    if len(points) < 2:
        return {"model": "DBSCAN-2D", "points": [], "clusters": []}

    labels = simple_dbscan_2d(points, eps=0.8, min_pts=2)
    out = []
    for i, label in enumerate(labels):
        out.append({
            "x": round(points[i][0], 3),
            "y": round(points[i][1], 3),
            "cluster": label,
            **meta[i],
        })
    clusters = {}
    for row in out:
        if row["cluster"] >= 0:
            clusters[row["cluster"]] = clusters.get(row["cluster"], 0) + 1
    return {
        "model": "DBSCAN-2D",
        "definition": "Trace latency x error-rate clustering (complements 3sigma/IQR)",
        "points": out,
        "clusters": [{"cluster_id": k, "size": v} for k, v in sorted(clusters.items())],
    }

"""扫描/监控 — 多维态势可视化（Plotly，无 emoji）."""

from __future__ import annotations

from collections import Counter
from typing import Any

from security_agent.timeutil import parse_iso

import pandas as pd
import plotly.graph_objects as go

from security_agent.demo.scenarios import LEVEL_SCORE, risks_to_cube_points

# 监控事件 type → (维度, 默认严重度分)
_EVENT_DIM: dict[str, tuple[str, int]] = {
    "高危新进程": ("进程", 4),
    "新进程": ("进程", 1),
    "敏感文件变更": ("路径", 3),
    "新增监听端口": ("网络", 3),
    "监听端口关闭": ("网络", 1),
    "登录失败": ("认证", 3),
    "无效用户登录尝试": ("认证", 3),
    "密码登录成功": ("认证", 2),
    "暴破疑似": ("认证", 4),
    "计划任务新增": ("计划", 3),
    "计划任务变更": ("计划", 3),
    "计划任务删除": ("计划", 2),
    "监控启动": ("系统", 0),
    "监控停止": ("系统", 0),
    "心跳": ("系统", 0),
    "监控错误": ("系统", 1),
}

_DIM_ORDER = ["进程", "路径", "网络", "认证", "计划", "系统", "其它"]

# 3D 图：禁止交互（防止滚动页面时误触旋转/缩放）
PLOTLY_3D_CONFIG: dict[str, object] = {
    "displayModeBar": False,
    "staticPlot": True,
}

# 2D 图表：全部静态展示（防误触）
PLOTLY_STATIC_CONFIG: dict[str, object] = {
    "displayModeBar": False,
    "staticPlot": True,
}


def _level_score(level: str) -> int:
    return LEVEL_SCORE.get(str(level), 1)


def monitor_events_to_cube_points(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """监控事件 → 与演练中心兼容的 cube_points."""
    dim_idx = {d: i for i, d in enumerate(_DIM_ORDER)}
    points: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        etype = str(ev.get("type", ""))
        dim, default_score = _EVENT_DIM.get(etype, ("其它", 1))
        lvl = str(ev.get("level", "信息"))
        score = max(_level_score(lvl), default_score)
        label = ev.get("name") or ev.get("path") or ev.get("local") or etype
        points.append(
            {
                "id": i,
                "label": str(label)[:24],
                "type": etype,
                "level": lvl,
                "severity": score,
                "x_type": dim_idx.get(dim, len(_DIM_ORDER) - 1),
                "y_severity": score,
                "z_source": 0,  # 0=实盘监控
                "layer": dim,
                "source": "monitor",
            }
        )
    return points


def merge_risks_and_events(
    risks: list[dict[str, Any]] | None,
    events: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    risk_pts = risks_to_cube_points(risks or [])
    for p in risk_pts:
        p["source"] = "scan"
        p["z_source"] = 0
    ev_pts = monitor_events_to_cube_points(events or [])
    return risk_pts + ev_pts


def posture_score(
    risks: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """简易安全态势分 0–100（越高越危险）."""
    weights = {"严重": 25, "高": 12, "中": 5, "低": 2, "信息": 0}
    total = 0
    counts: Counter[str] = Counter()
    for item in (risks or []) + (events or []):
        if item.get("type") in ("心跳", "监控启动", "监控停止"):
            continue
        lv = str(item.get("level", "信息"))
        counts[lv] += 1
        total += weights.get(lv, 1)
    score = min(100, total)
    if score >= 60:
        label, band = "高危", "bad"
    elif score >= 30:
        label, band = "关注", "warn"
    elif score > 0:
        label, band = "平稳", "ok"
    else:
        label, band = "良好", "ok"
    return {"score": score, "label": label, "band": band, "counts": dict(counts)}


def dimension_breakdown(
    risks: list[dict[str, Any]] | None,
    events: list[dict[str, Any]] | None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for r in risks or []:
        rows.append({"维度": "进程/权限", "条数": 1, "加权": _level_score(str(r.get("level", "中")))})
    for ev in events or []:
        etype = str(ev.get("type", ""))
        if etype in ("心跳", "监控启动", "监控停止"):
            continue
        dim = _EVENT_DIM.get(etype, ("其它", 1))[0]
        rows.append({"维度": dim, "条数": 1, "加权": _level_score(str(ev.get("level", "信息")))})
    if not rows:
        return pd.DataFrame(columns=["维度", "条数", "加权"])
    df = pd.DataFrame(rows)
    return df.groupby("维度", as_index=False).agg({"条数": "sum", "加权": "sum"})


def fig_cube_3d(points: list[dict[str, Any]], title: str = "多维风险分布") -> go.Figure | None:
    if not points:
        return None
    df = pd.DataFrame(points)
    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=df["x_type"],
                y=df["y_severity"],
                z=df["z_source"],
                mode="markers",
                text=df["label"],
                marker=dict(
                    size=9,
                    color=df["severity"],
                    colorscale="Reds",
                    showscale=True,
                    colorbar=dict(title="严重度"),
                ),
                customdata=df[["type", "level", "source", "layer"]],
                hovertemplate=(
                    "事件=%{customdata[0]}<br>等级=%{customdata[1]}"
                    "<br>来源=%{customdata[2]}<br>维度=%{customdata[3]}<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        title=title,
        height=420,
        autosize=True,
        margin=dict(l=0, r=0, t=36, b=0),
        scene=dict(
            dragmode=False,
            aspectmode="cube",
            xaxis=dict(
                title="类型/维度轴",
                tickvals=list(range(len(_DIM_ORDER))),
                ticktext=_DIM_ORDER,
            ),
            yaxis_title="严重度(1-4)",
            zaxis=dict(
                title="来源",
                tickvals=[0, 1],
                ticktext=["实盘", "扫描/合成"],
            ),
        ),
    )
    return fig


def fig_timeline(events: list[dict[str, Any]], title: str = "监控事件时间线") -> go.Figure | None:
    """按时间 × 严重度的实时散点."""
    filtered = [e for e in events if e.get("type") != "心跳"]
    if not filtered:
        return None
    rows = []
    for ev in filtered:
        t = parse_iso(ev.get("ts"))
        if t is None:
            continue
        rows.append(
            {
                "time": t,
                "severity": _level_score(str(ev.get("level", "信息"))),
                "type": ev.get("type", ""),
                "level": ev.get("level", ""),
            }
        )
    if not rows:
        return None
    df = pd.DataFrame(rows).sort_values("time")
    fig = go.Figure(
        data=[
            go.Scatter(
                x=df["time"],
                y=df["severity"],
                mode="markers",
                marker=dict(
                    size=10,
                    color=df["severity"],
                    colorscale="Reds",
                    showscale=False,
                ),
                text=df["type"],
                hovertemplate="%{text}<br>等级=%{customdata}<br>%{x}<extra></extra>",
                customdata=df["level"],
            )
        ]
    )
    fig.update_layout(
        title=title,
        height=280,
        xaxis_title="时间",
        yaxis=dict(title="严重度", tickvals=[1, 2, 3, 4], ticktext=["低", "中", "高", "严重"]),
        margin=dict(l=0, r=0, t=36, b=0),
    )
    return fig


def fig_dimension_radar(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None
    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=df["加权"].tolist() + [df["加权"].tolist()[0]],
                theta=df["维度"].tolist() + [df["维度"].tolist()[0]],
                fill="toself",
                name="风险加权",
            )
        ]
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True)),
        height=320,
        margin=dict(l=40, r=40, t=36, b=0),
        title="分维度风险雷达",
    )
    return fig


def fig_level_bars(counts: dict[str, int]) -> go.Figure | None:
    if not counts:
        return None
    order = ["严重", "高", "中", "低", "信息"]
    labels = [k for k in order if counts.get(k)]
    vals = [counts[k] for k in labels]
    colors = ["#ef5350", "#ffa726", "#64b5f6", "#90a4ae", "#546e7a"]
    fig = go.Figure(data=[go.Bar(x=labels, y=vals, marker_color=colors[: len(labels)])])
    fig.update_layout(title="等级分布", height=240, margin=dict(l=0, r=0, t=32, b=0))
    return fig

"""Trace 多类型可视化渲染 — 刻度与绘图区网格对齐."""

from __future__ import annotations

import html as html_lib
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from security_agent.audit.trace_chart_metrics import ChartSpec

_VIZ_LABEL: dict[str, str] = {
    "donut": "构成分析 · 环形图",
    "hbar": "排名对比 · 条形图",
    "gauge": "阈值监测 · 仪表盘",
    "line": "时序趋势 · 折线图",
    "gantt": "流程挖掘 · 甘特条",
    "radar": "多维评估 · 雷达图",
    "stat": "指标卡",
    "vbar": "对比 · 柱形图",
}

# 与 CSS --plot-label-w / --plot-val-w 一致
_PLOT_LABEL_W = "108px"
_PLOT_VAL_W = "56px"


def viz_meta_line(chart_type: str, unit: str, y_max: float | None) -> str:
    viz = _VIZ_LABEL.get(chart_type, chart_type)
    u = f"单位 {html_lib.escape(unit)}" if unit else ""
    y = f" · 刻度 0–{y_max:g}" if y_max is not None else ""
    return f'<p class="chart-meta">可视化：{html_lib.escape(viz)}{(" · " + u) if u else ""}{y}</p>'


def chart_footnote(spec: "ChartSpec") -> str:
    return (
        f'<p class="chart-def">{html_lib.escape(spec.definition)}</p>'
        f"{viz_meta_line(spec.chart_type, spec.unit, spec.y_max)}"
    )


def _chart_max(spec: "ChartSpec") -> float:
    if spec.y_max is not None:
        return float(spec.y_max)
    return max((b.value for b in spec.bars), default=1.0) or 1.0


def _linear_ticks(vmax: float, n: int = 5) -> list[float]:
    if vmax <= 0:
        return [0.0]
    if n < 2:
        return [0.0, vmax]
    return [round(vmax * i / (n - 1), 1 if vmax < 20 else 0) for i in range(n)]


def _format_val(value: float, unit: str) -> str:
    if unit == "%":
        return f"{value:.1f}"
    if unit == "分":
        return f"{value:.1f}"
    if unit in ("个", "项", "次", "ms"):
        return str(int(value))
    if value >= 10000:
        return f"{value/1000:.1f}k"
    return str(int(value)) if value == int(value) else f"{value:.1f}"


def _axis_ticks_html(vmax: float, unit: str) -> str:
    """刻度尺 HTML（放在 .plot-col 内，与条形轨道同宽）."""
    ticks = _linear_ticks(vmax)
    marks = []
    grids = []
    for t in ticks:
        left = (t / vmax * 100.0) if vmax else 0.0
        marks.append(
            f'<span class="axis-tick" style="left:{left:.2f}%">'
            f"{html_lib.escape(_format_val(t, unit))}</span>"
        )
    for t in ticks[1:-1]:
        left = (t / vmax * 100.0) if vmax else 0.0
        grids.append(f'<span class="axis-gridline" style="left:{left:.2f}%"></span>')
    unit_s = html_lib.escape(unit) if unit else ""
    return (
        f'<div class="plot-col plot-col-axis">'
        f'<div class="axis-x-rail">{"".join(marks)}'
        f'<span class="axis-unit-inline">({unit_s})</span></div>'
        f'<div class="axis-x-line"></div>'
        f'<div class="axis-track-grid">{"".join(grids)}</div></div>'
    )


def _wrap_plot_h(
    rows_html: str,
    spec: "ChartSpec",
    *,
    cols: str = "label-val",
    chart_class: str = "plot-rows",
) -> str:
    """水平图：标签列 + 绘图列 (+ 可选数值列) 与顶轴严格对齐."""
    vmax = _chart_max(spec)
    if cols == "label-only":
        header = (
            f'<div class="plot-h plot-h-2col">'
            f'<div class="plot-h-head plot-grid-2">'
            f'<div class="plot-label-spacer"></div>{_axis_ticks_html(vmax, spec.unit)}</div>'
        )
    else:
        header = (
            f'<div class="plot-h plot-h-3col">'
            f'<div class="plot-h-head plot-grid-3">'
            f'<div class="plot-label-spacer"></div>{_axis_ticks_html(vmax, spec.unit)}'
            f'<div class="plot-val-spacer"></div></div>'
        )
    return f'{header}<div class="{chart_class}">{rows_html}</div></div>'


def _wrap_plot_v(inner: str, spec: "ChartSpec") -> str:
    """柱形图：仅左侧 Y 刻度，X 为类别名（柱下），底部不再画数值横轴."""
    vmax = _chart_max(spec)
    ticks = list(reversed(_linear_ticks(vmax)))
    marks = []
    for t in ticks:
        bottom = (t / vmax * 100.0) if vmax else 0.0
        marks.append(
            f'<span class="axis-tick-y" style="bottom:{bottom:.2f}%">'
            f"{html_lib.escape(_format_val(t, spec.unit))}</span>"
        )
    unit = html_lib.escape(spec.unit)
    return (
        f'<div class="plot-v">'
        f'<div class="plot-v-y"><div class="axis-y-line"></div>'
        f'<div class="axis-y-rail">{"".join(marks)}</div>'
        f'<span class="axis-unit-y">{unit}</span></div>'
        f'<div class="plot-v-body">{inner}</div></div>'
    )


def render_donut(spec: "ChartSpec") -> str:
    total = sum(b.value for b in spec.bars) or 1.0
    stops: list[str] = []
    acc = 0.0
    legend = []
    for b in spec.bars:
        pct = b.value / total * 100.0
        if pct <= 0:
            continue
        stops.append(f"{b.color} {acc:.2f}% {acc + pct:.2f}%")
        acc += pct
        legend.append(
            f'<span class="donut-leg"><i style="background:{b.color}"></i>'
            f"{html_lib.escape(b.label)} {html_lib.escape(_format_val(b.value, spec.unit))}"
            f" ({pct:.0f}%)</span>"
        )
    if not stops:
        return ""
    grad = ", ".join(stops)
    center = html_lib.escape(_format_val(total, spec.unit))
    scale_legend = "".join(
        f"<li><i style=\"background:{html_lib.escape(b.color)}\"></i>"
        f"{html_lib.escape(b.label)}</li>"
        for b in spec.bars
    )
    return (
        f'<div class="donut-wrap" role="img">'
        f'<div class="donut-panel">'
        f'<div class="donut" style="background:conic-gradient({grad})">'
        f'<div class="donut-hole"><b>{center}</b><span>合计</span></div></div>'
        f'<div class="donut-side">'
        f'<div class="scale-box"><b>占比刻度</b><ul>{scale_legend}</ul>'
        f'<p class="scale-hint">环上数值 = 各段占合计比例</p></div>'
        f'<div class="donut-legend">{"".join(legend)}</div></div></div>'
        f"{chart_footnote(spec)}"
    )


def render_hbar(spec: "ChartSpec") -> str:
    mx = _chart_max(spec)
    rows = []
    for b in spec.bars:
        pct = min(100.0, (b.value / mx * 100.0) if mx else 0.0)
        rows.append(
            f'<div class="plot-row plot-grid-3">'
            f'<div class="plot-label">{html_lib.escape(b.label)}</div>'
            f'<div class="plot-col"><div class="bar-fill-h" style="width:{pct:.1f}%;background:{b.color}"></div></div>'
            f'<div class="plot-val">{html_lib.escape(_format_val(b.value, spec.unit))}</div></div>'
        )
    return _wrap_plot_h("".join(rows), spec) + chart_footnote(spec)


def render_gauge(spec: "ChartSpec") -> str:
    vmax = spec.y_max or 100.0
    rows = []
    for b in spec.bars:
        pct = min(100.0, b.value / vmax * 100.0)
        thr = (60.0 / vmax * 100.0) if vmax else 60.0
        rows.append(
            f'<div class="plot-row plot-grid-3">'
            f'<div class="plot-label">{html_lib.escape(b.label)}</div>'
            f'<div class="plot-col"><div class="bar-fill-h" style="width:{pct:.1f}%;background:{b.color}"></div>'
            f'<div class="bullet-threshold" style="left:{thr:.1f}%"></div></div>'
            f'<div class="plot-val">{html_lib.escape(_format_val(b.value, spec.unit))}</div></div>'
        )
    hint = '<p class="scale-hint">红色竖线 = 60 分参考阈值</p>' if vmax == 100 else ""
    return _wrap_plot_h("".join(rows), spec) + hint + chart_footnote(spec)


def render_gantt(spec: "ChartSpec") -> str:
    mx = _chart_max(spec)
    rows = []
    for b in spec.bars:
        pct = min(100.0, (b.value / mx * 100.0) if mx else 0.0)
        rows.append(
            f'<div class="plot-row plot-grid-2">'
            f'<div class="plot-label">{html_lib.escape(b.label)}</div>'
            f'<div class="plot-col"><div class="bar-fill-h gantt-inner" style="width:{pct:.1f}%;background:{b.color}">'
            f"{html_lib.escape(_format_val(b.value, spec.unit))}</div></div></div>"
        )
    return _wrap_plot_h("".join(rows), spec, cols="label-only") + chart_footnote(spec)


def render_line(spec: "ChartSpec") -> str:
    if len(spec.bars) < 2:
        return render_hbar(spec)
    vals = [b.value for b in spec.bars]
    mx, mn = max(vals) or 1.0, min(vals)
    pad = (mx - mn) * 0.1 if mx > mn else mx * 0.1 or 1
    lo, hi = mn - pad, mx + pad
    margin_l, margin_b, margin_t = 48, 32, 14
    w, h = 380, 168
    plot_w, plot_h = w - margin_l - 14, h - margin_b - margin_t
    n = len(spec.bars)
    grid_lines = []
    for t in _linear_ticks(hi - lo if hi > lo else hi, 5):
        y = margin_t + plot_h * (1 - (t - lo) / (hi - lo) if hi > lo else 0.5)
        grid_lines.append(
            f'<line x1="{margin_l}" y1="{y:.1f}" x2="{w - 10}" y2="{y:.1f}" class="axis-grid"/>'
        )
        grid_lines.append(
            f'<text x="{margin_l - 8}" y="{y + 4:.0f}" text-anchor="end" class="axis-tick-svg">'
            f"{html_lib.escape(_format_val(t, spec.unit))}</text>"
        )
    xs, ys, xlabels = [], [], []
    for i, b in enumerate(spec.bars):
        x = margin_l + plot_w * (i / (n - 1)) if n > 1 else margin_l + plot_w / 2
        y = margin_t + plot_h * (1 - (b.value - lo) / (hi - lo) if hi > lo else 0.5)
        xs.append(x)
        ys.append(y)
        xlabels.append(
            f'<text x="{x:.0f}" y="{h - 8}" text-anchor="middle" class="axis-tick-svg">'
            f"{html_lib.escape(b.label[:10])}</text>"
        )
    poly = " ".join(f"{xs[i]:.1f},{ys[i]:.1f}" for i in range(n))
    dots = "".join(
        f'<circle cx="{xs[i]:.0f}" cy="{ys[i]:.0f}" r="4" fill="{spec.bars[i].color}"/>'
        for i in range(n)
    )
    svg = (
        f'<svg class="line-chart" viewBox="0 0 {w} {h}" role="img">'
        f'<line x1="{margin_l}" y1="{margin_t + plot_h}" x2="{margin_l}" y2="{margin_t}" class="axis-line"/>'
        f'<line x1="{margin_l}" y1="{margin_t + plot_h}" x2="{w - 10}" y2="{margin_t + plot_h}" class="axis-line"/>'
        f"{''.join(grid_lines)}"
        f'<text x="{margin_l - 28}" y="{margin_t + 8}" class="axis-unit-svg">'
        f"{html_lib.escape(spec.unit)}</text>"
        f'<polyline points="{poly}" fill="none" stroke="#1565c0" stroke-width="2"/>'
        f"{dots}{''.join(xlabels)}</svg>"
    )
    return svg + chart_footnote(spec)


def render_radar(spec: "ChartSpec") -> str:
    """雷达图：刻度放右侧图例，顶点标注具体分值（避免刻度压在网格中央）."""
    n = len(spec.bars)
    if n < 2:
        return render_hbar(spec)
    if n <= 4:
        return render_hbar(spec)
    vmax = spec.y_max or 100.0
    cx, cy, r = 100, 105, 68
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    grid = []
    for ring in (0.25, 0.5, 0.75, 1.0):
        gp = " ".join(
            f"{cx + r * ring * math.cos(a):.1f},{cy + r * ring * math.sin(a):.1f}" for a in angles
        )
        grid.append(f'<polygon points="{gp}" class="radar-grid"/>')
    dp_parts = []
    vertex_labels = []
    for i, b in enumerate(spec.bars):
        rad = r * min(1.0, b.value / vmax)
        dp_parts.append(
            f"{cx + rad * math.cos(angles[i]):.1f},{cy + rad * math.sin(angles[i]):.1f}"
        )
        lx = cx + (r + 22) * math.cos(angles[i])
        ly = cy + (r + 22) * math.sin(angles[i])
        vertex_labels.append(
            f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" class="radar-lbl">'
            f"{html_lib.escape(b.label[:10])}</text>"
        )
        vertex_labels.append(
            f'<text x="{lx:.0f}" y="{ly + 12:.0f}" text-anchor="middle" class="radar-score">'
            f"{html_lib.escape(_format_val(b.value, spec.unit))}</text>"
        )
    dp = " ".join(dp_parts)
    scale_items = "".join(
        f"<li><span>{html_lib.escape(_format_val(vmax * ring, spec.unit))}</span>"
        f"<i>→ {'外圈' if ring == 1.0 else f'{int(ring*100)}% 半径'}</i></li>"
        for ring in (0.25, 0.5, 0.75, 1.0)
    )
    svg = (
        f'<div class="radar-layout"><svg class="radar-chart" viewBox="0 0 200 210" role="img">'
        f"{''.join(grid)}"
        f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - r}" class="axis-line"/>'
        f'<polygon points="{dp}" class="radar-fill"/>'
        f"{''.join(vertex_labels)}</svg>"
        f'<div class="radar-scale-box"><b>读图说明</b><ul>{scale_items}</ul>'
        f'<p>同心环 = 得分比例；顶点数字 = 该维度实际{html_lib.escape(spec.unit)}</p></div></div>'
    )
    return svg + chart_footnote(spec)


def render_stat_cards(spec: "ChartSpec") -> str:
    cards = []
    for b in spec.bars:
        cards.append(
            f'<div class="stat-card" style="border-color:{b.color}">'
            f'<b style="color:{b.color}">{html_lib.escape(_format_val(b.value, spec.unit or ""))}</b>'
            f"<span>{html_lib.escape(b.label)}</span></div>"
        )
    return f'<div class="stat-row">{"".join(cards)}</div>{chart_footnote(spec)}'


def render_vbar(spec: "ChartSpec") -> str:
    y_max = _chart_max(spec)
    cols = []
    for b in spec.bars:
        pct = min(100.0, (b.value / y_max * 100.0) if y_max else 0.0)
        if pct < 4 and b.value > 0:
            pct = 4.0
        cols.append(
            f'<div class="vbar-item">'
            f'<div class="vbar-val-top">{html_lib.escape(_format_val(b.value, spec.unit))}</div>'
            f'<div class="vbar-col"><div class="vbar-fill" style="height:{pct:.1f}%;background:{b.color}"></div></div>'
            f'<div class="vbar-label">{html_lib.escape(b.label)}</div></div>'
        )
    return _wrap_plot_v(f'<div class="vbar-chart">{"".join(cols)}</div>', spec) + chart_footnote(spec)


def render_chart(spec: "ChartSpec") -> str:
    if not spec.bars:
        return ""
    renderers = {
        "donut": render_donut,
        "hbar": render_hbar,
        "gauge": render_gauge,
        "line": render_line,
        "gantt": render_gantt,
        "radar": render_radar,
        "stat": render_stat_cards,
        "vbar": render_vbar,
    }
    return renderers.get(spec.chart_type or "vbar", render_vbar)(spec)

"""Trace HTML 可视化编排 — 多类型图表 + 步骤/阶段表."""

from __future__ import annotations

import base64
import html as html_lib
from io import BytesIO
from typing import Any

from security_agent.audit.trace_chart_metrics import ChartSpec, build_chart_specs
from security_agent.audit.trace_report_viz import _VIZ_LABEL, render_chart

_FLOW_STEP_CN = {
    "security_scan": "进程/路径扫描",
    "exposed_ports": "端口暴露",
    "system_health": "系统健康",
    "text_report": "文本报告",
    "html_report": "HTML 报告",
    "safety_evaluate": "三层防御",
    "terminal_exec": "安全执行",
    "route_alert": "告警路由",
    "block_process": "进程拦截",
}

_STAGE_LABELS: dict[str, str] = {
    "receive_request": "接收用户请求",
    "skill_flow_start": "开始 L2 固定流程",
    "skill_flow_end": "完成 L2 固定流程",
    "post_verify": "执行结果校验",
    "environment_probe": "环境探测 / 工具链",
    "environment_probe_result": "工具链结果汇总",
    "inference_decision": "LLM 推理决策",
    "safety_check": "安全校验",
    "execution": "命令或工具执行",
    "degradation": "服务降级",
}


def build_viz_strategy_html(facts: dict[str, Any], bundle: dict[str, Any]) -> str:
    """数据挖掘式选图策略说明（本 Trace 实际用到的图表类型）."""
    specs = build_chart_specs(facts, bundle)
    used = sorted({s.chart_type for s in specs if s.bars})
    if not used:
        return ""
    items = "".join(
        f"<li><b>{_VIZ_LABEL.get(t, t)}</b></li>" for t in used
    )
    return (
        '<section class="panel viz-strategy">'
        '<h2 style="margin:0 0 8px;font-size:15px;">可视化策略</h2>'
        '<p class="chart-def">按指标语义选图：构成→环形图，排名→条形图，阈值 KPI→仪表盘，'
        "阶段历时→甘特条，轮次趋势→折线，多维评分→雷达，离散指标→指标卡。</p>"
        f"<ul class=\"strategy-list\">{items}</ul></section>"
    )


def _step_result_text(st: dict[str, Any]) -> str:
    if st.get("risk_count") is not None:
        return f"风险 {st['risk_count']} 项"
    if st.get("risky_count") is not None:
        return f"高危暴露 {st['risky_count']} 个"
    if st.get("report_len") is not None:
        return f"报告 {st['report_len']} 字"
    if st.get("path"):
        return st["path"].split("/")[-1]
    if st.get("error"):
        return str(st["error"])[:80]
    return "完成" if st.get("ok", True) else "失败"


def _flow_step_table_html(steps: list[dict[str, Any]]) -> str:
    rows = []
    for st in steps:
        step = st.get("step") or f"步骤{st.get('index', '')}"
        label = _FLOW_STEP_CN.get(step, step)
        ok = st.get("ok", True)
        status = '<span style="color:#2e7d32">✓</span>' if ok else '<span style="color:#c62828">✗</span>'
        detail = html_lib.escape(_step_result_text(st))
        rows.append(
            f"<tr><td>{html_lib.escape(label)}</td><td>{status}</td><td>{detail}</td></tr>"
        )
    return (
        '<p class="chart-def">可视化：明细表（定性步骤结果，不用柱形刻度）。</p>'
        '<table class="step-table"><thead><tr><th>步骤</th><th>状态</th><th>结果</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _process_timeline_table_html(facts: dict[str, Any]) -> str:
    import html as html_lib

    rows = []
    skip = {"incident_spine_begin", "incident_spine_end"}
    for s in facts.get("timeline") or []:
        name = s.get("name", "")
        if name in skip:
            continue
        label = s.get("label") or _STAGE_LABELS.get(name, name)
        ms = int(s.get("ms") or 0)
        ms_s = f"{ms} ms" if ms else "—"
        rows.append(
            f"<tr><td>{html_lib.escape(label)}</td>"
            f"<td>{html_lib.escape(ms_s)}</td></tr>"
        )
    if not rows:
        return ""
    return (
        '<p class="chart-def">可视化：阶段明细表（补充无甘特/折线时的过程视图）。</p>'
        '<table class="step-table"><thead><tr><th>阶段</th><th>耗时</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _chart_sections(facts: dict[str, Any], bundle: dict[str, Any]) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for spec in build_chart_specs(facts, bundle):
        body = render_chart(spec)
        if body:
            sections.append((spec.title, body))
    return sections


def build_visual_sections(facts: dict[str, Any], bundle: dict[str, Any]) -> list[tuple[str, str]]:
    sections = _chart_sections(facts, bundle)
    flow = facts.get("flow")
    steps = facts.get("flow_steps") or []
    if steps and flow == "scan_report":
        sections.append(("L2 执行步骤（明细）", _flow_step_table_html(steps)))
    timeline_tbl = _process_timeline_table_html(facts)
    has_timing_chart = any(
        "耗时" in title or "轮次" in title for title, _ in sections
    )
    if timeline_tbl and not has_timing_chart:
        sections.append(("处置过程（阶段）", timeline_tbl))
    return sections


def _fig_to_b64(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build_chart_images(facts: dict[str, Any], bundle: dict[str, Any]) -> dict[str, str]:
    """Matplotlib 导出（类型与 HTML 策略一致）."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return {}

    images: dict[str, str] = {}
    plt.rcParams["font.sans-serif"] = [
        "PingFang SC",
        "Microsoft YaHei",
        "WenQuanYi Micro Hei",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    for spec in build_chart_specs(facts, bundle):
        if not spec.bars:
            continue
        labels = [b.label for b in spec.bars]
        values = [b.value for b in spec.bars]
        colors = [b.color for b in spec.bars]
        try:
            fig, ax = plt.subplots(figsize=(6, 3.6))
            ymax = spec.y_max if spec.y_max is not None else max(values) * 1.15 or 1
            ctype = spec.chart_type
            if ctype == "donut" and sum(values) > 0:
                ax.pie(values, labels=labels, colors=colors, autopct="%1.0f%%", startangle=90)
            elif ctype == "line" and len(values) >= 2:
                ax.plot(range(len(values)), values, marker="o", color="#1565c0")
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, rotation=15, ha="right")
                ax.set_ylabel(spec.unit or "")
                ax.grid(alpha=0.3)
            elif ctype == "gantt":
                ax.barh(labels, values, color=colors)
                ax.set_xlabel(spec.unit or "")
                ax.invert_yaxis()
            elif ctype == "radar" and len(values) >= 3:
                import numpy as np

                angles = np.linspace(0, 2 * np.pi, len(values), endpoint=False).tolist()
                vals = values + [values[0]]
                ang = angles + [angles[0]]
                ax = fig.add_subplot(111, polar=True)
                ax.plot(ang, vals, color="#1565c0")
                ax.fill(ang, vals, alpha=0.2, color="#1565c0")
                ax.set_xticks(angles)
                ax.set_xticklabels(labels)
            else:
                ax.bar(labels, values, color=colors)
                ax.set_ylim(0, ymax)
                ax.set_ylabel(spec.unit or "")
            ax.set_title(spec.title.split("·", 1)[-1].strip())
            if spec.y_max == 100.0 and ctype in ("gauge", "vbar", "hbar"):
                ax.axhline(60, color="#c62828", linestyle="--", linewidth=0.7, alpha=0.5)
            images[spec.chart_id] = _fig_to_b64(fig)
        except Exception:
            continue
    return images

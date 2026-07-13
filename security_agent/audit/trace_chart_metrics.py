"""Trace 可视化指标规格 — 每类图只绑定明确定义的业务度量."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 风险等级归一化（用于计数与配色）
_LEVEL_ORDER = ("critical", "高", "high", "中", "medium", "低", "low", "unknown")
_LEVEL_COLORS = {
    "critical": "#b71c1c",
    "高": "#c62828",
    "high": "#c62828",
    "中": "#e65100",
    "medium": "#e65100",
    "低": "#fbc02d",
    "low": "#fbc02d",
    "unknown": "#90a4ae",
}


def normalize_risk_level(level: Any) -> str:
    lv = str(level or "unknown").strip()
    low = lv.lower()
    if lv in ("高", "高危") or low in ("high", "critical"):
        return "高"
    if lv in ("中",) or low == "medium":
        return "中"
    if lv in ("低",) or low == "low":
        return "低"
    if low == "critical":
        return "严重"
    return lv or "未知"


def risk_by_level_counts(facts: dict[str, Any]) -> dict[str, int]:
    """从 risk_items 或 risk_by_level 汇总，键为展示用中文等级."""
    counts: dict[str, int] = {}
    items = facts.get("risk_items") or []
    if items:
        for r in items:
            k = normalize_risk_level(r.get("level"))
            counts[k] = counts.get(k, 0) + 1
        return counts
    raw = facts.get("risk_by_level") or {}
    for k, v in raw.items():
        nk = normalize_risk_level(k)
        counts[nk] = counts.get(nk, 0) + int(v)
    return counts


@dataclass
class MetricBar:
    label: str
    value: float
    color: str = "#1565c0"


@dataclass
class ChartSpec:
    """单张图的指标契约."""

    chart_id: str
    title: str
    definition: str  # 指标口径说明（显示在图下）
    unit: str
    y_max: float | None  # None = 按数据自适应
    bars: list[MetricBar] = field(default_factory=list)
    chart_type: str = "vbar"  # donut | hbar | gauge | line | gantt | radar | stat | vbar

    @property
    def has_data(self) -> bool:
        return any(b.value > 0 for b in self.bars) or (
            self.chart_type == "table" and bool(self.bars)
        )


def build_scan_report_charts(facts: dict[str, Any]) -> list[ChartSpec]:
    """扫描报告 L2：仅绘制有业务口径的图."""
    charts: list[ChartSpec] = []

    listen = int(facts.get("listen_count") or 0)
    risky = int(facts.get("risky_ports") or 0)
    safe = max(0, listen - risky)
    if listen > 0:
        charts.append(
            ChartSpec(
                chart_id="port_exposure",
                title="端口监听构成",
                definition="口径：全网卡监听端口总数；高危暴露 = 对 0.0.0.0/:: 监听且命中高危端口清单的条目数。",
                unit="个",
                y_max=None,
                chart_type="donut",
                bars=[
                    MetricBar("安全监听", float(safe), "#43a047"),
                    MetricBar("高危暴露", float(risky), "#c62828" if risky else "#a5d6a7"),
                ],
            )
        )

    by_level = risk_by_level_counts(facts)
    if by_level and sum(by_level.values()) > 0:
        ordered = sorted(
            by_level.items(),
            key=lambda x: (_LEVEL_ORDER.index(x[0]) if x[0] in _LEVEL_ORDER else 99, -x[1]),
        )
        charts.append(
            ChartSpec(
                chart_id="risk_level",
                title="风险等级分布",
                definition="口径：扫描结果 risk 列表按等级去重计数（非步骤伪分值）。",
                unit="项",
                y_max=None,
                chart_type="hbar" if len(ordered) > 2 else "donut",
                bars=[
                    MetricBar(lv, float(cnt), _LEVEL_COLORS.get(lv, "#5c6bc0"))
                    for lv, cnt in ordered
                ],
            )
        )

    health = facts.get("health") or {}
    hbars: list[MetricBar] = []
    for key, label, color, warn in (
        ("cpu_percent", "CPU", "#1e88e5", 80),
        ("memory_percent", "内存", "#7b1fa2", 85),
        ("disk_percent", "磁盘", "#00897b", 90),
    ):
        v = health.get(key)
        if v is not None:
            fv = float(v)
            hbars.append(
                MetricBar(
                    label,
                    fv,
                    "#c62828" if fv >= warn else "#43a047" if fv < 60 else "#fb8c00",
                )
            )
    if hbars:
        charts.append(
            ChartSpec(
                chart_id="system_health",
                title="系统资源占用",
                definition="口径：扫描时刻瞬时利用率；纵轴固定 0–100%。绿<60%，橙 60–阈值，红≥阈值。",
                unit="%",
                y_max=100.0,
                chart_type="gauge",
                bars=hbars,
            )
        )

    timeline = facts.get("timeline") or []
    skip = {"incident_spine_begin", "incident_spine_end"}
    return [c for c in charts if c.bars]


def build_secure_exec_charts(facts: dict[str, Any]) -> list[ChartSpec]:
    charts: list[ChartSpec] = []
    layers = facts.get("defense_layers") or []
    if layers:
        charts.append(
            ChartSpec(
                chart_id="defense_score",
                title="三层防御得分",
                definition="口径：各层 safety 评估 score，满分 100；虚线阈值为 60 分。",
                unit="分",
                y_max=100.0,
                chart_type="hbar",
                bars=[
                    MetricBar(
                        str(x.get("name_zh") or x.get("name"))
                        or {
                            "static_risk": "第1层 静态风险",
                            "dynamic_intent": "第2层 意图审计",
                            "restricted_exec": "第3层 受限执行",
                        }.get(str(x.get("layer", "")), str(x.get("layer", ""))),
                        float(x.get("score") or 0),
                        ["#3b82f6", "#10b981", "#f59e0b"][i % 3],
                    )
                    for i, x in enumerate(layers)
                ],
            )
        )

    timeline = facts.get("timeline") or []
    tbars = []
    for s in timeline:
        ms = int(s.get("ms") or 0)
        if ms > 0:
            tbars.append(
                MetricBar((s.get("label") or s.get("name", ""))[:10], float(ms), "#1565c0")
            )
    if tbars:
        charts.append(
            ChartSpec(
                chart_id="spine_timing",
                title="链路阶段耗时（防御）",
                definition="口径：Spine 阶段 duration_ms。",
                unit="ms",
                y_max=None,
                chart_type="gantt",
                bars=tbars,
            )
        )
    return charts


def build_l3_charts(facts: dict[str, Any], bundle: dict[str, Any]) -> list[ChartSpec]:
    charts: list[ChartSpec] = []
    tools = facts.get("tools") or []
    if tools:
        from collections import Counter

        top = Counter(tools).most_common(8)
        charts.append(
            ChartSpec(
                chart_id="tool_calls",
                title="L1 工具调用次数",
                definition="口径：ReasoningTrace 中记录的 tool 调用条目数（按工具名聚合）。",
                unit="次",
                y_max=None,
                chart_type="hbar",
                bars=[MetricBar(t[:16], float(c), "#5c6bc0") for t, c in top],
            )
        )
    llm = int(facts.get("llm_calls") or 0)
    tok = int(facts.get("tokens") or bundle.get("reasoning_report", {}).get("tokens_used") or 0)
    if llm > 0 or tok > 0:
        charts.append(
            ChartSpec(
                chart_id="llm_usage",
                title="模型消耗",
                definition="口径：本轮对话 LLM 调用次数与 Token 合计（含多轮工具循环）。",
                unit="",
                y_max=None,
                chart_type="stat",
                bars=[
                    MetricBar("LLM 调用", float(llm), "#00897b"),
                    MetricBar("Token", float(min(tok, 999999)), "#6a1b9a"),
                ],
            )
        )
    return charts


def build_spine_timing_chart(facts: dict[str, Any]) -> ChartSpec | None:
    timeline = facts.get("timeline") or []
    skip = {"incident_spine_begin", "incident_spine_end"}
    tbars: list[MetricBar] = []
    for s in timeline:
        name = s.get("name", "")
        if name in skip:
            continue
        ms = int(s.get("ms") or 0)
        if ms <= 0:
            continue
        label = (s.get("label") or name)[:12]
        color = "#1565c0" if ms < 500 else "#e65100" if ms < 2000 else "#c62828"
        tbars.append(MetricBar(label, float(ms), color))
    if not tbars:
        return None
    return ChartSpec(
        chart_id="spine_timing",
        title="链路阶段耗时",
        definition="口径：Incident Spine / SQLite 已落库阶段的 duration_ms。",
        unit="ms",
        y_max=None,
        chart_type="gantt",
        bars=tbars,
    )


def build_l3_execution_chart(facts: dict[str, Any]) -> ChartSpec | None:
    """L3 多轮 execution 阶段耗时."""
    exec_stages = [s for s in (facts.get("timeline") or []) if s.get("name") == "execution"]
    if len(exec_stages) < 2:
        return None
    bars = []
    for i, s in enumerate(exec_stages[:14]):
        ms = int(s.get("ms") or 0)
        if ms <= 0:
            ms = 1
        bars.append(MetricBar(f"第{i + 1}轮", float(ms), "#5c6bc0"))
    if not bars:
        return None
    return ChartSpec(
        chart_id="l3_execution",
        title="L3 工具执行轮次耗时",
        definition="口径：每轮 execution 阶段的 wall time（含 MCP/终端调用）。",
        unit="ms",
        y_max=None,
        chart_type="line",
        bars=bars,
    )


def _merge_chart(specs: list[ChartSpec], extra: ChartSpec | None) -> list[ChartSpec]:
    if not extra or not extra.bars:
        return specs
    if any(c.chart_id == extra.chart_id for c in specs):
        return specs
    return specs + [extra]


def _renumber_titles(specs: list[ChartSpec]) -> list[ChartSpec]:
    for i, spec in enumerate(specs, 1):
        base = spec.title.split("·", 1)[-1].strip() if "·" in spec.title else spec.title
        spec.title = f"图{i} · {base}"
    return specs


def build_chart_specs(facts: dict[str, Any], bundle: dict[str, Any]) -> list[ChartSpec]:
    flow = facts.get("flow") or ""
    specs: list[ChartSpec] = []
    if flow == "scan_report":
        specs = build_scan_report_charts(facts)
    elif flow == "secure_exec":
        specs = build_secure_exec_charts(facts)
        if not any(c.chart_id == "defense_score" for c in specs) and facts.get("score") is not None:
            specs.insert(
                0,
                ChartSpec(
                    chart_id="defense_overall",
                    title="安全评估得分",
                    definition="口径：三层防御综合评分（SQLite / audit 已记录字段）。",
                    unit="分",
                    y_max=100.0,
                    chart_type="gauge",
                    bars=[
                        MetricBar(
                            str(facts.get("verdict") or "综合"),
                            float(facts.get("score") or 0),
                            "#1e88e5",
                        )
                    ],
                ),
            )
    elif int(facts.get("llm_calls") or 0) > 0 or facts.get("tools"):
        specs = build_l3_charts(facts, bundle)
        specs = _merge_chart(specs, build_l3_execution_chart(facts))
    specs = _merge_chart(specs, build_spine_timing_chart(facts))
    if not specs:
        spine = build_spine_timing_chart(facts)
        if spine:
            specs = [spine]
    return _renumber_titles(specs)

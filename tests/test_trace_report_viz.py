"""多类型 Trace 图表渲染."""

from security_agent.audit.trace_chart_metrics import ChartSpec, MetricBar, build_scan_report_charts
from security_agent.audit.trace_report_viz import render_chart


def test_scan_uses_mixed_chart_types():
    facts = {
        "listen_count": 10,
        "risky_ports": 2,
        "risk_items": [{"level": "高"}],
        "health": {"cpu_percent": 10, "memory_percent": 70, "disk_percent": 80},
    }
    specs = build_scan_report_charts(facts)
    types = {s.chart_type for s in specs}
    assert "donut" in types
    assert "gauge" in types
    assert len(types) >= 2


def test_render_donut_html():
    spec = ChartSpec(
        chart_id="t",
        title="测试",
        definition="口径测试",
        unit="个",
        y_max=None,
        chart_type="donut",
        bars=[MetricBar("A", 3, "#0f0"), MetricBar("B", 1, "#f00")],
    )
    html = render_chart(spec)
    assert "donut-wrap" in html
    assert "conic-gradient" in html
    assert "donut-scale" in html


def test_hbar_has_axis_rail():
    spec = ChartSpec(
        chart_id="t",
        title="测试",
        definition="口径",
        unit="次",
        y_max=10.0,
        chart_type="hbar",
        bars=[MetricBar("A", 3, "#00f"), MetricBar("B", 7, "#f00")],
    )
    html = render_chart(spec)
    assert "plot-grid-3" in html
    assert "axis-x-rail" in html
    assert "plot-col" in html

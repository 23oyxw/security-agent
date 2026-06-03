"""Trace 图表指标规格."""

from security_agent.audit.trace_chart_metrics import (
    build_scan_report_charts,
    normalize_risk_level,
    risk_by_level_counts,
)


def test_normalize_risk_level():
    assert normalize_risk_level("高") == "高"
    assert normalize_risk_level("HIGH") == "高"


def test_scan_charts_have_definitions():
    facts = {
        "listen_count": 12,
        "risky_ports": 2,
        "risk_count": 2,
        "health": {"cpu_percent": 6.3, "memory_percent": 72.4, "disk_percent": 72.0},
        "risk_items": [{"level": "高"}, {"level": "高"}],
        "timeline": [{"name": "receive_request", "label": "接收", "ms": 400}],
    }
    charts = build_scan_report_charts(facts)
    assert len(charts) >= 3
    titles = [c.chart_id for c in charts]
    assert "port_exposure" in titles
    assert "system_health" in titles
    assert all(c.definition and c.unit for c in charts)
    assert charts[0].bars[0].label == "安全监听"
    assert risk_by_level_counts(facts)["高"] == 2

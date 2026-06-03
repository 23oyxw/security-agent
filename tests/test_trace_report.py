"""Trace 纪要 TXT + HTML 可视化."""

from security_agent.audit.trace_report import bundle_to_html, bundle_to_text, extract_facts


def _sample_bundle():
    return {
        "trace_id": "trace-ea477762286c",
        "sqlite_trace": {
            "user_message": "安全执行 `ls -la /tmp`",
            "status": "completed",
            "created_at": "2026-05-30 08:34:44",
            "completed_at": "2026-05-30 08:34:45",
            "stages": [
                {"name": "receive_request", "duration_ms": 907, "data": {}},
                {"name": "skill_flow_start", "duration_ms": 100, "data": {"flow": "secure_exec"}},
                {
                    "name": "skill_flow_end",
                    "duration_ms": 14,
                    "data": {
                        "flow": "secure_exec",
                        "ok": True,
                        "command": "ls -la /tmp",
                        "verdict": "allow",
                        "score": 93.25,
                        "exit_code": 0,
                    },
                },
                {"name": "post_verify", "duration_ms": 4, "data": {"ok": True, "exit_code": 0, "message": "total 100"}},
            ],
        },
        "reasoning_report": {"llm_calls": 0, "tokens_used": 0},
        "audit_events": [],
    }


def test_minutes_txt_format():
    text = bundle_to_text(_sample_bundle())
    assert "执行纪要" in text
    assert "一、议题与结论" in text
    assert "二、处置过程" in text
    assert "defense_result" not in text
    assert "ls -la /tmp" in text


def test_scan_report_html_highlights_risks():
    bundle = {
        "trace_id": "t-scan",
        "sqlite_trace": {"user_message": "生成扫描报告", "stages": []},
        "audit_events": [
            {
                "action": "skill_flow_end",
                "detail": {
                    "flow": "scan_report",
                    "ok": True,
                    "risk_count": 3,
                    "report_html_path": "/data/reports/security_report_x.html",
                    "report_len": 1200,
                    "steps": [
                        {"step": "security_scan", "ok": True, "risk_count": 2},
                        {"step": "exposed_ports", "ok": True, "risky_count": 1},
                    ],
                    "scan": {"risk_count": 3, "risks": [{"level": "high"}, {"level": "high"}, {"level": "low"}]},
                },
            }
        ],
    }
    html = bundle_to_html(bundle)
    assert "风险项" in html
    assert "执行分析" in html
    assert "风险明细" in html
    assert "图1" in html or "端口" in html
    assert "chart-def" in html
    assert "可视化策略" in html
    assert "donut" in html or "bullet" in html or "gauge" in html or "hbar" in html


def test_export_links_skill_flow_subtrace():
    """卷宗应合并 L2 runner 的 skill_flow_end（短 trace_id）."""
    from security_agent.audit.spine import export_incident_bundle

    bundle = export_incident_bundle("trace-851c521d916f")
    actions = [e.get("action") for e in bundle.get("audit_events") or []]
    assert "skill_flow_end" in actions
    f = extract_facts(bundle)
    assert f.get("flow") == "scan_report"
    assert f.get("risk_count") is not None or f.get("flow_steps")
    assert f.get("risk_items") or f.get("risk_count") is not None


def test_extract_defense_layers_from_audit():
    bundle = _sample_bundle()
    bundle["audit_events"] = [
        {
            "action": "skill_flow_end",
            "detail": {
                "flow": "secure_exec",
                "ok": True,
                "defense": {
                    "overall_verdict": "allow",
                    "overall_score": 90,
                    "layers": [
                        {"layer": "static_risk", "score": 95, "verdict": "pass"},
                    ],
                },
            },
        }
    ]
    f = extract_facts(bundle)
    assert len(f["defense_layers"]) == 1

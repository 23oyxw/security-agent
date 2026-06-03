"""Trace 阶段耗时与时间戳口径."""

from security_agent.audit.trace_report import _stage_duration_deltas, extract_facts


def test_cumulative_durations_converted_to_deltas():
    stages = [
        {"name": "receive_request", "duration_ms": 900},
        {"name": "skill_flow_start", "duration_ms": 1100},
        {"name": "skill_flow_end", "duration_ms": 1200},
    ]
    assert _stage_duration_deltas(stages) == [900, 200, 100]


def test_extract_facts_timeline_uses_deltas():
    bundle = {
        "trace_id": "trace-test-timing",
        "sqlite_trace": {
            "user_message": "告警响应",
            "status": "completed",
            "created_at": "2026-05-30T10:00:00+08:00",
            "completed_at": "2026-05-30T10:00:02+08:00",
            "stages": [
                {"name": "receive_request", "duration_ms": 500, "timestamp": "2026-05-30T10:00:00+08:00"},
                {"name": "skill_flow_start", "duration_ms": 800, "data": {"flow": "alert_response"}},
                {
                    "name": "skill_flow_end",
                    "duration_ms": 2000,
                    "data": {
                        "flow": "alert_response",
                        "ok": True,
                        "alert_event": {"ts": "2026-05-30T09:55:00+08:00", "message": "CPU高"},
                        "alert_responses": [{"skill": "healthcheck", "status": "ok"}],
                    },
                },
            ],
        },
        "audit_events": [],
    }
    f = extract_facts(bundle)
    ms_list = [s["ms"] for s in f["timeline"]]
    assert ms_list == [500, 300, 1200]
    assert f.get("alert_occurred_at")
    assert f["created_at"].startswith("2026-05-30 10:00:00")

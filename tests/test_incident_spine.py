"""事件脊柱、预算、熔断、降级阶梯."""

from __future__ import annotations

from security_agent.audit.spine import export_incident_bundle, incident_spine, new_trace_id
from security_agent.resilience.budget import RequestBudget
from security_agent.resilience.circuit import get_circuit
from security_agent.resilience.degradation import DegradationLevel


def test_request_budget_slice():
    b = RequestBudget(total_sec=10.0, trace_id="trace-test")
    assert b.remaining() <= 10.0
    assert b.slice_timeout("llm") <= 10.0


def test_circuit_opens_after_failures():
    cb = get_circuit("test:unit", failure_threshold=2, open_sec=30.0)
    cb.record_failure("e1")
    cb.record_failure("e2")
    assert cb.allow() is False
    cb.record_success()
    assert cb.allow() is True


def test_incident_spine_stages():
    tid = new_trace_id()
    with incident_spine("测试脊柱", trace_id=tid) as spine:
        spine.stage("receive_request", {"ok": True})
        spine.set_degradation(DegradationLevel.S2_RULE, "test")
        assert spine.trace_id == tid
    bundle = export_incident_bundle(tid)
    assert bundle["trace_id"] == tid


if __name__ == "__main__":
    test_request_budget_slice()
    test_circuit_opens_after_failures()
    test_incident_spine_stages()
    print("test_incident_spine: ok")

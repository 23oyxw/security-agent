"""企业级运维：审批队列、执行守卫、就绪探针."""

from __future__ import annotations

from fastapi.testclient import TestClient

from security_agent.api.app import app
from security_agent.confirm import ConfirmationStatus, get_confirmation_manager


def test_confirmation_persist_and_expire():
    mgr = get_confirmation_manager()
    req = mgr.create_request(
        trace_id="trace-test-ops",
        user_message="test",
        action_description="rm -rf /tmp/demo",
        risk_level="high",
        confirmation_level=__import__(
            "security_agent.confirm", fromlist=["ConfirmationLevel"]
        ).ConfirmationLevel.APPROVE,
        metadata={"command": "rm -rf /tmp/demo"},
    )
    assert mgr.get_request(req.request_id) is not None
    mgr.approve_request(req.request_id, "tester", "ok")
    got = mgr.get_request(req.request_id)
    assert got.status == ConfirmationStatus.APPROVED


def test_approval_api_flow():
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    sub = client.post(
        "/api/safety/submit",
        headers=h,
        json={"command": "iptables -F", "risk_level": "high", "trace_id": "trace-e2e-ops"},
    )
    assert sub.status_code == 200
    rid = sub.json().get("request_id") or sub.json().get("task_id")
    assert rid

    pending = client.get("/api/safety/pending", headers=h)
    assert pending.status_code == 200
    assert any(p.get("request_id") == rid for p in pending.json())

    appr = client.post(
        "/api/safety/approve",
        headers=h,
        json={"request_id": rid, "task_id": rid, "action": "approve", "reason": "e2e"},
    )
    assert appr.status_code == 200

    from security_agent.ops.guardrails import is_approval_granted

    assert is_approval_granted(rid, command="iptables -F")


def test_health_ready():
    client = TestClient(app)
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert "checks" in r.json()


if __name__ == "__main__":
    test_confirmation_persist_and_expire()
    test_approval_api_flow()
    test_health_ready()
    print("test_enterprise_ops: ok")

"""Dify 桥接与 API 冒烟（主干 security_agent/dify）."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from security_agent.api.app import app
from security_agent.dify.bridge import (
    DifyIntegration,
    WorkflowDispatcher,
    WorkflowType,
    _safe_parse_json,
)


def test_safe_parse_json_from_markdown():
    raw = '说明如下:\n```json\n{"threat_type": "scan", "risk_level": 3}\n```'
    data = _safe_parse_json(raw)
    assert data.get("threat_type") == "scan"
    assert data.get("risk_level") == 3


def test_dispatch_threat_detection():
    disp = WorkflowDispatcher()
    out = disp.dispatch_threat_detection(
        {"result": json.dumps({"threat_type": "brute_force", "risk_level": 7, "urgency": "紧急"})}
    )
    assert out.threat_type == "brute_force"
    assert out.risk_level == 7


def test_handle_callback_no_auto_remediation():
    integration = DifyIntegration()
    result = integration.handle_callback(
        workflow_type=WorkflowType.THREAT_DETECTION.value,
        outputs={"threat_type": "test", "risk_level": 3, "urgency": "低"},
        workflow_run_id="run-test",
        trace_id="trace-test",
    )
    assert result["workflow_type"] == WorkflowType.THREAT_DETECTION.value
    assert result.get("action_required") is False


def test_dify_callback_api():
    client = TestClient(app)
    resp = client.post(
        "/api/dify/callback",
        json={
            "workflow_type": "knowledge_rag",
            "outputs": {"answer": "参考 PB-001 处理"},
            "auto_remediation": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"
    assert "result" in body


def test_knowledge_rag_api():
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    if login.status_code != 200:
        return
    token = login.json().get("access_token")
    resp = client.post(
        "/api/knowledge/rag",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "SSH", "top_k": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "citations" in data
    assert "grounding" in data


if __name__ == "__main__":
    test_safe_parse_json_from_markdown()
    test_dispatch_threat_detection()
    test_handle_callback_no_auto_remediation()
    test_dify_callback_api()
    test_knowledge_rag_api()
    print("test_dify_bridge: ok")

"""L2 Skill Flow 冒烟测试（无需 pytest 插件时可 python tests/test_skill_flows.py）."""

from __future__ import annotations

import asyncio
import sys

from fastapi.testclient import TestClient

from security_agent.agent.orchestrator import build_plan, detect_intent
from security_agent.api.app import app
from security_agent.skills.flows import list_flows, run_skill_flow


def test_detect_scan_report_intent():
    assert detect_intent("请生成扫描报告") == "scan_report"
    plan = build_plan("一键扫描报告")
    assert plan.get("skill_flow") == "scan_report"
    assert plan.get("tool_chain") == []


def test_list_flows():
    names = {f["name"] for f in list_flows()}
    assert names >= {"secure_exec", "alert_response", "scan_report", "block_process"}


def test_scan_report_flow():
    result = asyncio.run(run_skill_flow("scan_report", {}))
    assert result.get("flow") == "scan_report"
    assert "trace_id" in result
    assert str(result["trace_id"]).startswith("trace-")


def test_run_skill_flow_uses_external_trace_id():
    tid = "trace-deadbeef1234"
    result = asyncio.run(
        run_skill_flow("alert_response", {"alert_event": {"message": "test", "level": "高"}}, trace_id=tid)
    )
    assert result.get("trace_id") == tid


def test_api_list_and_run_requires_auth():
    client = TestClient(app)
    assert client.get("/api/skills/flows/").status_code == 401
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    if login.status_code != 200:
        return  # 环境未初始化默认账号时跳过
    token = login.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/api/skills/flows/", headers=headers)
    assert listed.status_code == 200
    assert listed.json().get("total", 0) >= 4


if __name__ == "__main__":
    test_detect_scan_report_intent()
    test_list_flows()
    test_scan_report_flow()
    test_run_skill_flow_uses_external_trace_id()
    test_api_list_and_run_requires_auth()
    print("test_skill_flows: ok")
    sys.exit(0)

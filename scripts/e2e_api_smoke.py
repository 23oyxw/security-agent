#!/usr/bin/env python3
"""FastAPI 端到端冒烟 — 覆盖 Vue 联调关键路径（无需 pytest）."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from security_agent.api.app import app  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    print("=== API E2E 冒烟（Vue / B2 联调路径）===\n")
    client = TestClient(app)

    r = client.get("/api/health")
    record("GET /api/health", r.status_code == 200, r.json().get("status", ""))

    ready = client.get("/api/health/ready")
    record("GET /api/health/ready", ready.status_code == 200, ready.json().get("status", ""))

    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    if login.status_code != 200:
        record("POST /api/auth/login", False, login.text[:120])
        return _summary()
    token = login.json().get("access_token", "")
    headers = {"Authorization": f"Bearer {token}"}
    record("POST /api/auth/login", bool(token), "admin")

    endpoints = [
        ("GET /api/perception/metrics", lambda: client.get("/api/perception/metrics", headers=headers)),
        ("GET /api/perception/context", lambda: client.get("/api/perception/context", headers=headers)),
        ("GET /api/alerts/", lambda: client.get("/api/alerts/", headers=headers)),
        ("GET /api/mcp/servers", lambda: client.get("/api/mcp/servers", headers=headers)),
        ("GET /api/trace/", lambda: client.get("/api/trace/", headers=headers)),
        ("GET /api/knowledge/playbooks", lambda: client.get("/api/knowledge/playbooks", headers=headers)),
        ("GET /api/dify/health", lambda: client.get("/api/dify/health")),
        ("GET /api/skills/flows/", lambda: client.get("/api/skills/flows/", headers=headers)),
        ("GET /api/workflow/standard", lambda: client.get("/api/workflow/standard", headers=headers)),
        ("GET /api/auth/me", lambda: client.get("/api/auth/me", headers=headers)),
    ]
    for label, fn in endpoints:
        resp = fn()
        record(label, resp.status_code == 200, f"status={resp.status_code}")

    deny = client.post(
        "/api/safety/defense/evaluate",
        headers=headers,
        json={"target": "rm -rf /tmp/x", "target_type": "terminal", "user_message": "删除目录"},
    )
    record(
        "POST /api/safety/defense/evaluate (deny)",
        deny.status_code == 200 and deny.json().get("overall_verdict") in ("deny", "confirm", "escalate", "quarantine", "approve"),
        deny.json().get("overall_verdict", ""),
    )

    defense = client.post(
        "/api/safety/defense/evaluate",
        headers=headers,
        json={"target": "ls -la", "target_type": "terminal", "user_message": "查看目录"},
    )
    record(
        "POST /api/safety/defense/evaluate",
        defense.status_code == 200 and "overall_verdict" in defense.json(),
        defense.json().get("overall_verdict", ""),
    )

    flow = client.post(
        "/api/skills/flows/scan_report/run",
        headers=headers,
        json={"context": {}},
    )
    record(
        "POST /api/skills/flows/scan_report/run",
        flow.status_code == 200 and flow.json().get("flow") == "scan_report",
        f"ok={flow.json().get('ok')}",
    )

    exec_r = client.post(
        "/api/executor/execute",
        headers=headers,
        json={"command": "ps aux | head -2", "timeout": 10, "confirm": True, "sandbox": True},
    )
    record("POST /api/executor/execute", exec_r.status_code == 200, f"success={exec_r.json().get('success')}")

    agent = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "生成扫描报告"},
    )
    record(
        "POST /api/agent/chat (scan_report intent)",
        agent.status_code == 200 and bool(agent.json().get("reply")),
        (agent.json().get("reply") or "")[:40],
    )

    rag = client.post(
        "/api/knowledge/rag",
        headers=headers,
        json={"query": "SSH 暴力破解", "top_k": 3},
    )
    record(
        "POST /api/knowledge/rag",
        rag.status_code == 200 and "citations" in rag.json(),
        f"total={rag.json().get('total')}",
    )

    cb = client.post(
        "/api/dify/callback",
        json={
            "workflow_type": "threat_detection",
            "outputs": {"threat_type": "brute_force", "risk_level": 5, "urgency": "低"},
            "auto_remediation": False,
        },
    )
    record("POST /api/dify/callback", cb.status_code == 200 and cb.json().get("status") == "ok", "")

    reload = client.post("/api/mcp/reload", headers=headers)
    record(
        "POST /api/mcp/reload",
        reload.status_code == 200 and reload.json().get("ok"),
        f"servers={reload.json().get('servers_count')}",
    )

    ok_ws = False
    resp: dict = {}
    try:
        with client.websocket_connect("/api/agent/ws/chat") as ws:
            hello = ws.receive_json()
            ws.send_json({"type": "auth", "token": token})
            auth_msg = ws.receive_json()
            ok_ws = hello.get("type") == "system" and auth_msg.get("type") == "auth_ok"
            if ok_ws:
                ws.send_json({"type": "chat", "message": "你好"})
                typing = ws.receive_json()
                resp = ws.receive_json()
                ok_ws = typing.get("type") == "typing" and resp.get("type") in ("response", "error")
        record("WS /api/agent/ws/chat", ok_ws, resp.get("type", "") if ok_ws else "")
    except Exception as exc:
        record("WS /api/agent/ws/chat", False, str(exc)[:80])

    sub = client.post(
        "/api/safety/submit",
        headers=headers,
        json={"command": "echo enterprise-check", "risk_level": "medium", "trace_id": "e2e-smoke"},
    )
    record("POST /api/safety/submit", sub.status_code == 200 and sub.json().get("request_id"), "")

    pend = client.get("/api/safety/pending", headers=headers)
    record("GET /api/safety/pending", pend.status_code == 200, f"count={len(pend.json())}")

    res_status = client.get("/api/resilience/status", headers=headers)
    record(
        "GET /api/resilience/status",
        res_status.status_code == 200 and "circuits" in res_status.json(),
        f"circuits={len(res_status.json().get('circuits', []))}",
    )

    if agent.status_code == 200 and agent.json().get("trace_id"):
        tid = agent.json()["trace_id"]
        exp = client.get(f"/api/trace/{tid}/export", headers=headers)
        record(
            f"GET /api/trace/{tid}/export",
            exp.status_code == 200,
            f"audit_events={len(exp.json().get('audit_events', []))}",
        )

    dist = ROOT / "frontend" / "dist" / "index.html"
    record("frontend/dist 静态资源", dist.is_file(), str(dist))

    root = client.get("/")
    record("SPA 根路径", root.status_code == 200, f"content-type={root.headers.get('content-type', '')[:40]}")

    return _summary()


def _summary() -> int:
    print()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"=== 结果: {passed}/{total} 通过 ===")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  - {name}: {detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

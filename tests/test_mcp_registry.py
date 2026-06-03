"""MCP 热插拔注册中心冒烟."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from security_agent.api.app import app
from security_agent.mcp.registry import get_mcp_registry, reload_mcp_plugins


def test_reload_plugins():
    result = reload_mcp_plugins()
    assert result.get("ok") is True
    assert result.get("servers_count", 0) >= 1


def test_api_reload():
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    if login.status_code != 200:
        return
    token = login.json()["access_token"]
    r = client.post("/api/mcp/reload", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


if __name__ == "__main__":
    test_reload_plugins()
    test_api_reload()
    print("test_mcp_registry: ok")
    sys.exit(0)

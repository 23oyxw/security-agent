"""监听端口变化监测 — 暴露面与新增监听."""

from __future__ import annotations

from typing import Any

import psutil

from security_agent import config


def snapshot_listeners() -> dict[tuple[str, int], dict[str, Any]]:
    """键 (bind_ip, port) → 元数据."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != psutil.CONN_LISTEN or not conn.laddr:
                continue
            ip = conn.laddr.ip or "0.0.0.0"
            port = int(conn.laddr.port)
            key = (ip, port)
            out[key] = {
                "pid": conn.pid,
                "local": f"{ip}:{port}",
                "port": port,
                "risky": port in config.EXPOSED_RISKY_PORTS,
                "public_bind": ip in ("0.0.0.0", "::", "::0", ""),
            }
    except (psutil.AccessDenied, PermissionError):
        pass
    return out


def diff_listeners(
    previous: dict[tuple[str, int], dict[str, Any]],
    current: dict[tuple[str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for key, meta in current.items():
        if key not in previous:
            level = "严重" if meta.get("risky") and meta.get("public_bind") else "高"
            events.append(
                {
                    "type": "新增监听端口",
                    "level": level,
                    "port": meta["port"],
                    "local": meta["local"],
                    "pid": meta.get("pid"),
                    "message": f"新监听 {meta['local']} pid={meta.get('pid')}"
                    + (" [高危端口+全网卡]" if meta.get("risky") and meta.get("public_bind") else ""),
                }
            )
    for key, meta in previous.items():
        if key not in current:
            events.append(
                {
                    "type": "监听端口关闭",
                    "level": "信息",
                    "port": meta["port"],
                    "local": meta["local"],
                    "message": f"监听已关闭 {meta['local']}",
                }
            )
    return events

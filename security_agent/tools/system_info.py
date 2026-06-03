"""System introspection tools."""

from __future__ import annotations

import json
import os
from typing import Any

import psutil

from security_agent import config
from security_agent.scanner.engine import is_elevated


def get_system_health() -> dict[str, Any]:
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "platform": config.platform_label(),
        "elevated": is_elevated(),
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "memory_percent": mem.percent,
        "memory_available_gb": round(mem.available / (1024**3), 2),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "boot_time": psutil.boot_time(),
    }


def get_process_detail(pid: int) -> dict[str, Any]:
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            return {
                "ok": True,
                "pid": pid,
                "name": p.name(),
                "username": p.username(),
                "status": p.status(),
                "cpu_percent": p.cpu_percent(),
                "memory_percent": p.memory_percent(),
                "cmdline": " ".join(p.cmdline()[:30]),
                "create_time": p.create_time(),
            }
    except psutil.NoSuchProcess:
        return {"ok": False, "message": f"进程不存在: {pid}"}
    except psutil.AccessDenied:
        return {"ok": False, "message": f"无权查看 PID {pid}"}


def list_network_connections(limit: int = 50) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for conn in psutil.net_connections(kind="inet")[:limit]:
            rows.append(
                {
                    "pid": conn.pid,
                    "local": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "",
                    "remote": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "",
                    "status": conn.status,
                }
            )
    except (psutil.AccessDenied, PermissionError):
        return [{"error": "权限不足，无法列出网络连接（需 root）"}]
    return rows


def check_sensitive_paths() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path_str in config.SENSITIVE_PATHS:
        exists = os.path.exists(path_str)
        writable = os.access(path_str, os.W_OK) if exists else False
        out.append(
            {
                "path": path_str,
                "exists": exists,
                "writable_by_current_user": writable,
            }
        )
    return out


def check_exposed_ports() -> dict[str, Any]:
    """检测对全网卡监听的高危端口（伪装窃密/端口暴露）."""
    risky = config.EXPOSED_RISKY_PORTS
    listeners: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != psutil.CONN_LISTEN or not conn.laddr:
                continue
            ip = conn.laddr.ip
            port = conn.laddr.port
            if ip not in ("0.0.0.0", "::", "::0", ""):
                continue
            row = {
                "pid": conn.pid,
                "local": f"{ip}:{port}",
                "port": port,
                "risky": port in risky,
            }
            listeners.append(row)
            if port in risky:
                alerts.append(
                    {
                        "type": "端口暴露",
                        "port": port,
                        "pid": conn.pid,
                        "local": row["local"],
                        "level": "高",
                        "message": f"高危端口 {port} 对全网卡监听，存在暴露与未授权访问风险",
                    }
                )
    except (psutil.AccessDenied, PermissionError):
        return {
            "ok": False,
            "message": "权限不足，无法枚举监听端口（建议 root 或 sudo ss -tlnp）",
            "listeners": [],
            "alerts": [],
        }
    return {
        "ok": True,
        "listener_count": len(listeners),
        "risky_count": len(alerts),
        "listeners": listeners[:80],
        "alerts": alerts,
    }


def full_security_check() -> dict[str, Any]:
    from security_agent.scanner.engine import run_security_scan

    exposed = check_exposed_ports()
    scan = run_security_scan()
    if exposed.get("alerts"):
        merged = list(scan.get("risks", []))
        merged.extend(exposed["alerts"])
        scan = {**scan, "risks": merged, "risk_count": len(merged)}
    return {
        "health": get_system_health(),
        "scan": scan,
        "sensitive_paths": check_sensitive_paths(),
        "exposed_ports": exposed,
        "connections_sample": list_network_connections(30),
    }

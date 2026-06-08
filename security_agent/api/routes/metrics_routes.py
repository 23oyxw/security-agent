"""Prometheus 指标端点 + 动态阈值 API.

GET /api/metrics          Prometheus text 格式指标
GET /api/metrics/json     JSON 格式（Dashboard 直接消费）
"""

from __future__ import annotations

import time
from typing import Any

import psutil
from fastapi import APIRouter, Depends

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User
from security_agent.monitor.dynamic_threshold import get_dynamic_threshold

router = APIRouter()


def _collect_metrics() -> dict[str, Any]:
    """采集系统指标."""
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    load = psutil.getloadavg()
    boot = psutil.boot_time()

    return {
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "net_bytes_sent": net.bytes_sent,
        "net_bytes_recv": net.bytes_recv,
        "load_1m": round(load[0], 2),
        "load_5m": round(load[1], 2),
        "load_15m": round(load[2], 2),
        "uptime_seconds": int(time.time() - boot),
        "process_count": len(psutil.pids()),
    }


@router.get("/api/metrics")
async def prometheus_metrics():
    """Prometheus text 格式指标端点."""
    m = _collect_metrics()
    dt = get_dynamic_threshold()

    lines = [
        "# HELP security_agent_cpu_percent Current CPU usage percentage",
        "# TYPE security_agent_cpu_percent gauge",
        f"security_agent_cpu_percent {m['cpu_percent']}",
        "# HELP security_agent_memory_percent Current memory usage percentage",
        "# TYPE security_agent_memory_percent gauge",
        f"security_agent_memory_percent {m['memory_percent']}",
        "# HELP security_agent_disk_percent Current disk usage percentage",
        "# TYPE security_agent_disk_percent gauge",
        f"security_agent_disk_percent {m['disk_percent']}",
        "# HELP security_agent_load_1m System load 1-minute average",
        "# TYPE security_agent_load_1m gauge",
        f"security_agent_load_1m {m['load_1m']}",
        "# HELP security_agent_uptime_seconds System uptime in seconds",
        "# TYPE security_agent_uptime_seconds gauge",
        f"security_agent_uptime_seconds {m['uptime_seconds']}",
        "# HELP security_agent_process_count Total process count",
        "# TYPE security_agent_process_count gauge",
        f"security_agent_process_count {m['process_count']}",
        "# HELP security_agent_threshold_cpu Dynamic CPU threshold",
        "# TYPE security_agent_threshold_cpu gauge",
        f"security_agent_threshold_cpu {dt['cpu_threshold']}",
        "# HELP security_agent_threshold_memory Dynamic memory threshold",
        "# TYPE security_agent_threshold_memory gauge",
        f"security_agent_threshold_memory {dt['memory_threshold']}",
        "# HELP security_agent_threshold_disk Dynamic disk threshold",
        "# TYPE security_agent_threshold_disk gauge",
        f"security_agent_threshold_disk {dt['disk_threshold']}",
        "",
    ]
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")


@router.get("/api/metrics/json")
async def metrics_json():
    """JSON 格式指标（Dashboard 消费）."""
    m = _collect_metrics()
    dt = get_dynamic_threshold()
    return {
        **m,
        "dynamic_thresholds": dt,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


@router.get("/api/metrics/thresholds")
async def metrics_thresholds():
    """动态阈值详情."""
    dt = get_dynamic_threshold()
    return {
        **dt,
        "history_size": dt.get("history_size", 0),
        "last_updated": dt.get("last_updated", ""),
    }

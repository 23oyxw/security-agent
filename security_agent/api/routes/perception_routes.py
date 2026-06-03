"""① 多维感知路由"""

import os
import time
from fastapi import APIRouter, Depends
from security_agent.api.deps import get_current_user
from security_agent.api.models import SystemMetricsResponse, LogQueryRequest, LogEntry
from security_agent.auth.models import User

router = APIRouter()


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_metrics(user: User = Depends(get_current_user)):
    """获取系统指标"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        load = os.getloadavg()
        net = psutil.net_io_counters()
        boot = psutil.boot_time()
        procs = len(psutil.pids())
        return SystemMetricsResponse(
            cpu_percent=cpu,
            memory_percent=mem.percent,
            disk_percent=disk.percent,
            load_avg=list(load),
            network_io={"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv},
            uptime_seconds=time.time() - boot,
            process_count=procs,
            timestamp=time.time(),
        )
    except Exception as e:
        return SystemMetricsResponse(
            cpu_percent=0, memory_percent=0, disk_percent=0,
            load_avg=[0, 0, 0], network_io={"bytes_sent": 0, "bytes_recv": 0},
            uptime_seconds=0, process_count=0, timestamp=time.time(),
        )


@router.get("/logs")
async def get_logs(source: str = "syslog", limit: int = 50, level: str = None,
                   user: User = Depends(get_current_user)):
    """获取日志"""
    logs = []
    log_paths = {
        "syslog": "/var/log/syslog",
        "auth": "/var/log/auth.log",
        "audit": "/var/log/audit/audit.log",
    }
    path = log_paths.get(source, "/var/log/syslog")
    try:
        if os.path.exists(path):
            with open(path, "r", errors="ignore") as f:
                lines = f.readlines()[-limit:]
                for line in lines:
                    logs.append({"timestamp": "", "level": "INFO", "source": source, "message": line.strip()})
    except PermissionError:
        logs.append({"timestamp": "", "level": "WARN", "source": source, "message": "权限不足，无法读取日志"})
    return {"source": source, "count": len(logs), "logs": logs}


@router.get("/context")
async def get_proactive_context(user: User = Depends(get_current_user)):
    """主动感知快照（结构化，供 Agent / 仪表盘）."""
    from security_agent.agent.perception import get_proactive_snapshot, get_system_context

    snapshot = get_proactive_snapshot()
    return {
        "snapshot": snapshot,
        "markdown": get_system_context()[:8000],
        "summary": snapshot.get("summary", {}),
    }
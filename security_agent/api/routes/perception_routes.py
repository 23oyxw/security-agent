"""① 多维感知路由 — 基础指标 + OS 深度感知 + 根因分析"""

import os
import sys
import time
from typing import Optional
from fastapi import APIRouter, Depends, Query
from security_agent.api.deps import get_current_user
from security_agent.api.models import SystemMetricsResponse, LogQueryRequest, LogEntry
from security_agent.auth.models import User

router = APIRouter()


def _disk_root() -> str:
    if sys.platform == "win32":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def _safe_load_avg(cpu_percent: float) -> list[float]:
    try:
        if hasattr(os, "getloadavg"):
            return [float(x) for x in os.getloadavg()]
    except (OSError, AttributeError):
        pass
    # Windows 无 getloadavg：用 CPU 利用率近似 1m 负载（相对核数）
    try:
        import psutil
        cores = max(psutil.cpu_count(logical=True) or 1, 1)
        load1 = round((cpu_percent / 100.0) * cores, 2)
        return [load1, load1, load1]
    except Exception:
        return [0.0, 0.0, 0.0]


@router.get("/metrics", response_model=SystemMetricsResponse)
async def get_metrics(user: User = Depends(get_current_user)):
    """获取系统指标 — 分项采集，避免单项失败导致整页归零"""
    cpu = mem_pct = disk_pct = 0.0
    load = [0.0, 0.0, 0.0]
    net = {"bytes_sent": 0, "bytes_recv": 0}
    uptime = 0.0
    procs = 0
    try:
        import psutil
        cpu = float(psutil.cpu_percent(interval=0.3))
        mem_pct = float(psutil.virtual_memory().percent)
        try:
            disk_pct = float(psutil.disk_usage(_disk_root()).percent)
        except Exception:
            disk_pct = float(psutil.disk_usage("/").percent)
        load = _safe_load_avg(cpu)
        nio = psutil.net_io_counters()
        if nio:
            net = {"bytes_sent": nio.bytes_sent, "bytes_recv": nio.bytes_recv}
        uptime = max(0.0, time.time() - psutil.boot_time())
        procs = len(psutil.pids())
    except Exception:
        pass
    return SystemMetricsResponse(
        cpu_percent=cpu,
        memory_percent=mem_pct,
        disk_percent=disk_pct,
        load_avg=load,
        network_io=net,
        uptime_seconds=uptime,
        process_count=procs,
        timestamp=time.time(),
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


# ---- OS 深度感知（赛题核心需求）----

@router.get("/os/snapshot")
async def os_full_snapshot(user: User = Depends(get_current_user)):
    """OS 环境全面感知快照 — 一次性采集进程/网络/磁盘/日志/僵尸进程."""
    from security_agent.tools.os_sensing import full_system_snapshot
    return await full_system_snapshot()


@router.get("/os/processes")
async def os_processes(top_n: int = Query(20, ge=1, le=100), user: User = Depends(get_current_user)):
    """进程列表（按 CPU 排序）."""
    from security_agent.tools.os_sensing import sense_processes
    return await sense_processes(top_n=top_n)


@router.get("/os/connections")
async def os_connections(user: User = Depends(get_current_user)):
    """网络连接感知 (ss/netstat)."""
    from security_agent.tools.os_sensing import sense_connections
    return await sense_connections()


@router.get("/os/ports")
async def os_listening_ports(user: User = Depends(get_current_user)):
    """监听端口列表."""
    from security_agent.tools.os_sensing import sense_listening_ports
    return await sense_listening_ports()


@router.get("/os/lsof")
async def os_lsof(pid: Optional[int] = None, port: Optional[int] = None,
                   user: User = Depends(get_current_user)):
    """lsof 感知 — 按 PID 或端口查看打开的文件/连接."""
    from security_agent.tools.os_sensing import sense_lsof
    return await sense_lsof(pid=pid, port=port)


@router.get("/os/journal")
async def os_journal(unit: Optional[str] = None, priority: str = "err",
                      lines: int = 50, since: str = "1h ago",
                      user: User = Depends(get_current_user)):
    """journalctl 日志感知."""
    from security_agent.tools.os_sensing import sense_journal
    return await sense_journal(unit=unit, priority=priority, lines=lines, since=since)


@router.get("/os/disk")
async def os_disk(user: User = Depends(get_current_user)):
    """磁盘使用率感知."""
    from security_agent.tools.os_sensing import sense_disk, sense_large_files
    disk = await sense_disk()
    large = await sense_large_files()
    return {"disk_usage": disk, "large_files": large}


@router.get("/os/zombies")
async def os_zombies(user: User = Depends(get_current_user)):
    """僵尸进程检测."""
    from security_agent.tools.os_sensing import sense_zombie_processes
    return await sense_zombie_processes()


@router.get("/os/load")
async def os_load(user: User = Depends(get_current_user)):
    """系统负载 + 内存 + uptime."""
    from security_agent.tools.os_sensing import sense_load
    return await sense_load()


# ---- 智能根因分析（赛题评分项）----

@router.get("/root-cause")
async def root_cause_analysis(user: User = Depends(get_current_user)):
    """智能根因分析 — 自动检测系统异常并给出根因 + 处置建议."""
    from security_agent.agent.root_cause import get_root_cause_analyzer
    analyzer = get_root_cause_analyzer()
    report = await analyzer.analyze()
    return report.to_dict()

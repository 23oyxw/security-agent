"""OS 环境深度感知工具集 — 封装 lsof/netstat/journalctl 等底层命令.

赛题要求: Agent 能够自动调用底层工具获取进程、网络、日志等实时上下文。
此模块提供标准化的 OS 感知接口，供 MCP Tools 和 Agent 调用。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 执行辅助
# ---------------------------------------------------------------------------

async def _run_cmd(cmd: list[str], timeout: float = 15.0) -> tuple[str, str, int]:
    """异步执行系统命令，返回 (stdout, stderr, returncode)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        return "", f"命令超时 ({timeout}s)", -1
    except FileNotFoundError:
        return "", f"命令未找到: {cmd[0]}", -1
    except Exception as e:
        return "", str(e), -1


# ---------------------------------------------------------------------------
# 进程感知
# ---------------------------------------------------------------------------

async def sense_processes(top_n: int = 20) -> Dict[str, Any]:
    """获取系统进程快照（ps aux + 排序）."""
    stdout, stderr, rc = await _run_cmd([
        "ps", "aux", "--sort=-pcpu"
    ])
    if rc != 0:
        return {"ok": False, "error": stderr}

    lines = stdout.strip().split("\n")
    header = lines[0] if lines else ""
    procs = []
    for line in lines[1:top_n+1]:
        parts = line.split(None, 10)
        if len(parts) >= 11:
            procs.append({
                "user": parts[0],
                "pid": parts[1],
                "cpu": parts[2],
                "mem": parts[3],
                "vsz": parts[4],
                "rss": parts[5],
                "stat": parts[7],
                "start": parts[8],
                "time": parts[9],
                "command": parts[10][:200],
            })
    return {"ok": True, "processes": procs, "total_lines": len(lines) - 1}


async def sense_lsof(pid: Optional[int] = None, port: Optional[int] = None) -> Dict[str, Any]:
    """lsof 感知：按 PID 或端口查看打开的文件/连接."""
    cmd = ["lsof", "-nP"]
    if pid:
        cmd.extend(["-p", str(pid)])
    if port:
        cmd.extend(["-i", f":{port}"])
    stdout, stderr, rc = await _run_cmd(cmd, timeout=10.0)
    if rc != 0:
        return {"ok": False, "error": stderr or "lsof 执行失败"}

    entries = []
    for line in stdout.strip().split("\n")[1:50]:  # 限制返回量
        parts = line.split(None, 8)
        if len(parts) >= 9:
            entries.append({
                "command": parts[0],
                "pid": parts[1],
                "user": parts[2],
                "fd": parts[3],
                "type": parts[4],
                "device": parts[5],
                "size": parts[6],
                "node": parts[7],
                "name": parts[8][:300],
            })
    return {"ok": True, "entries": entries, "total": len(entries)}


# ---------------------------------------------------------------------------
# 网络感知
# ---------------------------------------------------------------------------

async def sense_connections(protos: str = "tcp,udp") -> Dict[str, Any]:
    """netstat/ss 感知网络连接状态."""
    # 优先用 ss，回退 netstat
    stdout, stderr, rc = await _run_cmd(["ss", "-tulnp"])
    tool = "ss"
    if rc != 0:
        stdout, stderr, rc = await _run_cmd(["netstat", "-tulnp"])
        tool = "netstat"

    if rc != 0:
        return {"ok": False, "error": stderr}

    connections = []
    for line in stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 5 and ("LISTEN" in line or "ESTAB" in line or "udp" in line.lower()):
            local = parts[3] if len(parts) > 3 else ""
            remote = parts[4] if len(parts) > 4 else ""
            process_info = parts[-1] if len(parts) > 5 else ""
            connections.append({
                "proto": parts[0],
                "state": parts[1] if len(parts) > 1 else "",
                "local": local,
                "remote": remote,
                "process": process_info[:100],
            })

    return {"ok": True, "tool": tool, "connections": connections[:50], "total": len(connections)}


async def sense_listening_ports() -> Dict[str, Any]:
    """获取所有监听端口."""
    stdout, stderr, rc = await _run_cmd(["ss", "-tlnp"])
    if rc != 0:
        stdout, stderr, rc = await _run_cmd(["netstat", "-tlnp"])

    if rc != 0:
        return {"ok": False, "error": stderr}

    ports = []
    seen = set()
    for line in stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 4:
            local = parts[3]
            if local not in seen:
                seen.add(local)
                port_match = re.search(r':(\d+)$', local)
                ports.append({
                    "address": local,
                    "port": int(port_match.group(1)) if port_match else 0,
                    "process": parts[-1] if len(parts) > 4 else "",
                })
    return {"ok": True, "ports": ports, "total": len(ports)}


# ---------------------------------------------------------------------------
# 日志感知
# ---------------------------------------------------------------------------

async def sense_journal(
    unit: Optional[str] = None,
    priority: str = "err",
    lines: int = 50,
    since: str = "1h ago",
) -> Dict[str, Any]:
    """journalctl 日志感知 — 按 unit/priority/time 过滤."""
    cmd = ["journalctl", "--no-pager", "-q", f"-n{lines}", f"-p{priority}", f"--since={since}"]
    if unit:
        cmd.extend(["-u", unit])
    stdout, stderr, rc = await _run_cmd(cmd, timeout=10.0)
    if rc != 0:
        return {"ok": False, "error": stderr}

    entries = []
    for line in stdout.strip().split("\n"):
        if line.strip():
            entries.append(line[:500])
    return {"ok": True, "entries": entries, "total": len(entries)}


async def sense_syslog(
    lines: int = 50,
    keyword: Optional[str] = None,
) -> Dict[str, Any]:
    """读取 /var/log/syslog 或 /var/log/messages."""
    log_path = "/var/log/syslog"
    import os
    if not os.path.exists(log_path):
        log_path = "/var/log/messages"
    if not os.path.exists(log_path):
        return {"ok": False, "error": "未找到 syslog/messages 日志文件"}

    cmd = ["tail", f"-n{lines}", log_path]
    if keyword:
        cmd = ["grep", "-i", keyword, log_path]
    stdout, stderr, rc = await _run_cmd(cmd, timeout=10.0)
    if rc != 0:
        return {"ok": False, "error": stderr}

    entries = [line[:500] for line in stdout.strip().split("\n") if line.strip()]
    return {"ok": True, "log_path": log_path, "entries": entries, "total": len(entries)}


# ---------------------------------------------------------------------------
# 磁盘/文件系统感知
# ---------------------------------------------------------------------------

async def sense_disk() -> Dict[str, Any]:
    """磁盘使用率感知."""
    stdout, stderr, rc = await _run_cmd(["df", "-h", "--output=source,size,used,avail,pcent,target"])
    if rc != 0:
        return {"ok": False, "error": stderr}

    disks = []
    for line in stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 6 and not parts[0].startswith("tmpfs"):
            disks.append({
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "avail": parts[3],
                "use_percent": parts[4],
                "mount": parts[5],
            })
    return {"ok": True, "disks": disks}


async def sense_large_files(path: str = "/var/log", top_n: int = 10) -> Dict[str, Any]:
    """扫描大文件（日志堆积检测）."""
    stdout, stderr, rc = await _run_cmd(
        ["find", path, "-type", "f", "-size", "+10M", "-exec", "ls", "-lhS", "{}", "+"],
        timeout=30.0,
    )
    if rc != 0:
        return {"ok": False, "error": stderr}

    files = []
    for line in stdout.strip().split("\n")[:top_n]:
        parts = line.split()
        if len(parts) >= 9:
            files.append({
                "permissions": parts[0],
                "size": parts[4],
                "date": f"{parts[5]} {parts[6]} {parts[7]}",
                "path": parts[8],
            })
    return {"ok": True, "files": files, "total": len(files)}


# ---------------------------------------------------------------------------
# 系统状态感知
# ---------------------------------------------------------------------------

async def sense_load() -> Dict[str, Any]:
    """系统负载 + 内存 + uptime."""
    results = {}

    # load average
    stdout, _, rc = await _run_cmd(["cat", "/proc/loadavg"])
    if rc == 0:
        parts = stdout.split()
        results["load_avg"] = {
            "1min": parts[0] if len(parts) > 0 else "",
            "5min": parts[1] if len(parts) > 1 else "",
            "15min": parts[2] if len(parts) > 2 else "",
        }

    # uptime
    stdout, _, rc = await _run_cmd(["uptime", "-p"])
    if rc == 0:
        results["uptime"] = stdout.strip()

    # memory
    stdout, _, rc = await _run_cmd(["free", "-h"])
    if rc == 0:
        lines = stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 6:
                results["memory"] = {
                    "total": parts[1],
                    "used": parts[2],
                    "free": parts[3],
                    "available": parts[6] if len(parts) > 6 else "",
                }

    return {"ok": True, **results}


async def sense_zombie_processes() -> Dict[str, Any]:
    """僵尸进程检测."""
    stdout, stderr, rc = await _run_cmd(["ps", "aux"])
    if rc != 0:
        return {"ok": False, "error": stderr}

    zombies = []
    for line in stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 8 and "Z" in parts[7]:
            zombies.append({
                "user": parts[0],
                "pid": parts[1],
                "stat": parts[7],
                "command": " ".join(parts[10:])[:200],
            })

    return {
        "ok": True,
        "zombie_count": len(zombies),
        "zombies": zombies,
        "alert": len(zombies) > 0,
    }


# ---------------------------------------------------------------------------
# 综合感知快照（Agent 调用入口）
# ---------------------------------------------------------------------------

async def full_system_snapshot() -> Dict[str, Any]:
    """一次性采集全面系统状态 — 供 Agent 感知环境使用."""
    results = await asyncio.gather(
        sense_processes(top_n=10),
        sense_load(),
        sense_disk(),
        sense_listening_ports(),
        sense_zombie_processes(),
        sense_journal(priority="err", lines=10, since="30min ago"),
        return_exceptions=True,
    )

    def _safe(r: Any) -> Dict[str, Any]:
        if isinstance(r, Exception):
            return {"ok": False, "error": str(r)}
        return r  # type: ignore

    return {
        "ok": True,
        "snapshot_time": __import__("security_agent.timeutil", fromlist=["now_iso"]).now_iso(),
        "processes": _safe(results[0]),
        "system_load": _safe(results[1]),
        "disk": _safe(results[2]),
        "network_ports": _safe(results[3]),
        "zombies": _safe(results[4]),
        "recent_errors": _safe(results[5]),
    }
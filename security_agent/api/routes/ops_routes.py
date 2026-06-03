"""运维操作路由 — 进程清理 / CPU 压测 / 系统加速."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import signal
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


# ── 进程清理 ───────────────────────────────────────────────
@router.get("/processes/candidates")
async def cleanup_candidates():
    """扫描可清理的进程（僵尸/无用/高资源占用）."""
    try:
        result: dict[str, Any] = {"zombies": [], "idle": [], "heavy": []}

        # 1) 僵尸进程
        ps = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=10,
        )
        for line in ps.stdout.splitlines()[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            stat = parts[7] if len(parts) > 7 else ""
            pid = parts[1]
            cmd = parts[10] if len(parts) > 10 else ""
            # 僵尸进程
            if "Z" in stat:
                result["zombies"].append({
                    "pid": int(pid), "user": parts[0], "stat": stat,
                    "cmd": cmd[:120],
                })

        # 2) 可清理的高内存进程（排除系统关键进程）
        critical = {
            "systemd", "kthreadd", "sshd", "bash", "zsh",
            "python3", "node", "uvicorn", "gunicorn", "nginx",
            "postgres", "mysql", "docker", "containerd",
        }
        mem = subprocess.run(
            ["ps", "aux", "--sort=-%mem"], capture_output=True, text=True, timeout=10,
        )
        for line in mem.stdout.splitlines()[1:21]:  # top 20 by memory
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            pid = parts[1]
            cpu = float(parts[2]) if parts[2].replace(".", "").isdigit() else 0
            mem_pct = float(parts[3]) if parts[3].replace(".", "").isdigit() else 0
            cmd = parts[10] if len(parts) > 10 else ""
            cmd_name = cmd.split()[0].split("/")[-1] if cmd else ""

            # 内存 > 1% 且不在关键列表中的进程
            if mem_pct > 1.0 and cmd_name not in critical:
                result["heavy"].append({
                    "pid": int(pid), "user": parts[0],
                    "cpu_percent": cpu, "mem_percent": mem_pct,
                    "cmd": cmd[:120], "cmd_name": cmd_name,
                })

        # 3) 空闲进程（长时间 idle 的用户进程）
        idle = subprocess.run(
            ["ps", "eo", "pid,user,stat,etime,comm", "--sort=-etime"],
            capture_output=True, text=True, timeout=10,
        )
        for line in idle.stdout.splitlines()[1:30]:
            parts = line.split()
            if len(parts) < 5:
                continue
            pid, user, stat, etime, comm = parts[0], parts[1], parts[2], parts[3], parts[4]
            if user == "root" or comm in ("systemd", "kthreadd", "sshd", "bash"):
                continue
            # 超过 24 小时的用户进程
            if "-" in etime or (":" in etime and etime.count(":") == 2):
                days = 0
                if "-" in etime:
                    days_part, rest = etime.split("-", 1)
                    days = int(days_part) if days_part.isdigit() else 0
                if days > 0:
                    result["idle"].append({
                        "pid": int(pid), "user": user, "stat": stat,
                        "runtime": etime, "comm": comm, "days": days,
                    })

        result["total_candidates"] = (
            len(result["zombies"]) + len(result["idle"]) + len(result["heavy"])
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/processes/cleanup")
async def cleanup_processes(body: dict | None = None):
    """清理指定进程（需传 pid 列表或按类别清理）."""
    body = body or {}
    pids = body.get("pids")
    category = body.get("category", "zombies")
    if not pids and category == "zombies":
        # 自动获取僵尸进程 PID
        ps = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
        pids = []
        for line in ps.stdout.splitlines()[1:]:
            parts = line.split(None, 10)
            if len(parts) > 7 and "Z" in parts[7]:
                try:
                    pids.append(int(parts[1]))
                except ValueError:
                    pass

    if not pids:
        return {"cleaned": 0, "message": "无进程需要清理"}

    cleaned = []
    errors = []
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
            cleaned.append(pid)
        except ProcessLookupError:
            errors.append({"pid": pid, "error": "进程不存在"})
        except PermissionError:
            errors.append({"pid": pid, "error": "无权限"})
        except Exception as e:
            errors.append({"pid": pid, "error": str(e)})

    return {"cleaned": len(cleaned), "pids": cleaned, "errors": errors}


@router.get("/processes/summary")
async def process_summary():
    """进程总览."""
    ps = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
    lines = ps.stdout.strip().splitlines()[1:]
    
    by_user: dict[str, int] = {}
    zombies = 0
    for line in lines:
        parts = line.split()
        if len(parts) < 8:
            continue
        user = parts[0]
        by_user[user] = by_user.get(user, 0) + 1
        if "Z" in parts[7]:
            zombies += 1

    return {
        "total_processes": len(lines),
        "zombies": zombies,
        "by_user": dict(sorted(by_user.items(), key=lambda x: -x[1])[:10]),
    }


# ── CPU 压测 / 加速 ─────────────────────────────────────────
@router.get("/cpu/info")
async def cpu_info():
    """CPU 信息."""
    try:
        cpu_count = os.cpu_count() or 1
        model = ""
        freq = ""
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line and not model:
                    model = line.split(":")[1].strip()
                if "cpu MHz" in line and not freq:
                    freq = line.split(":")[1].strip() + " MHz"

        # 当前负载
        load = [float(x) for x in open("/proc/loadavg").read().split()[:3]]
        
        # CPU 使用率
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.5, percpu=True)
        
        return {
            "model": model or "Unknown",
            "cores": cpu_count,
            "frequency": freq or "N/A",
            "load_avg": load,
            "per_core_percent": cpu_pct,
            "avg_cpu_percent": round(sum(cpu_pct) / len(cpu_pct), 1) if cpu_pct else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cpu/stress")
async def cpu_stress(duration: int = 10, cores: int = 0):
    """多核 CPU 压测.
    
    Args:
        duration: 压测时长（秒），默认10
        cores: 使用核心数，0=全部
    """
    if duration > 120:
        raise HTTPException(400, "最长压测 120 秒")
    
    cores = cores or os.cpu_count() or 1
    
    script_path = "/home/oy0/security-agent/scripts/stress_cpu.sh"
    if os.path.exists(script_path):
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", script_path, "--multi", "--duration", str(duration),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=duration + 30)
            return {
                "status": "completed",
                "duration": duration,
                "cores": cores,
                "output": stdout.decode()[-3000:],
                "errors": stderr.decode()[-500:] if stderr else None,
            }
        except asyncio.TimeoutError:
            return {"status": "timeout", "duration": duration}
    else:
        # 内置纯 Python 压测
        import time
        import multiprocessing

        def _burn(end_time: float):
            while time.time() < end_time:
                _ = sum(i * i for i in range(10000))

        end = time.time() + duration
        procs = []
        for _ in range(cores):
            p = multiprocessing.Process(target=_burn, args=(end,))
            p.start()
            procs.append(p)

        for p in procs:
            p.join(timeout=duration + 5)
            if p.is_alive():
                p.terminate()

        return {
            "status": "completed",
            "duration": duration,
            "cores": cores,
            "output": f"内核压测完成: {cores} 核心 × {duration} 秒",
        }


# ── 系统加速/优化 ─────────────────────────────────────────
@router.post("/system/optimize")
async def system_optimize():
    """一键系统优化：清理缓存/僵尸/无用进程."""
    results: dict[str, Any] = {"actions": []}

    # 1) 清理僵尸进程
    ps = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
    zombies_cleaned = 0
    for line in ps.stdout.splitlines()[1:]:
        parts = line.split(None, 10)
        if len(parts) > 7 and "Z" in parts[7]:
            try:
                pid = int(parts[1])
                # 对僵尸进程的父进程发送 SIGCHLD
                ppid = parts[2] if len(parts) > 2 else ""
                os.kill(pid, signal.SIGKILL)
                zombies_cleaned += 1
            except (ValueError, ProcessLookupError, PermissionError):
                pass
    results["actions"].append({
        "action": "清理僵尸进程",
        "count": zombies_cleaned,
    })

    # 2) 清理系统缓存（如果有 root 权限）
    try:
        proc = subprocess.run(
            ["sync"], capture_output=True, timeout=10,
        )
        results["actions"].append({"action": "sync 磁盘缓存", "ok": proc.returncode == 0})
    except Exception:
        results["actions"].append({"action": "sync 磁盘缓存", "ok": False})

    # 3) 查找并报告大文件
    try:
        find = subprocess.run(
            ["find", "/tmp", "-type", "f", "-size", "+100M", "-exec", "ls", "-lh", "{}", ";"],
            capture_output=True, text=True, timeout=15,
        )
        large_files = find.stdout.strip().splitlines()[:5] if find.stdout.strip() else []
        results["actions"].append({
            "action": "扫描大文件 (/tmp > 100M)",
            "found": len(large_files),
            "files": large_files,
        })
    except Exception:
        results["actions"].append({"action": "扫描大文件", "error": "超时"})

    return results
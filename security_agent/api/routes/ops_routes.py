"""运维操作路由 — 进程清理 / CPU 压测 / 系统加速."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import signal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

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
async def cleanup_processes(body: dict | None = None, user: User = Depends(get_current_user)):
    """清理僵尸/指定进程 (需 operator+ 权限)."""
    if user.role not in ("operator", "admin"):
        raise HTTPException(403, detail="需要 operator 或 admin 权限")
    body = body or {}
    pids = body.get("pids")
    category = body.get("category", "zombies")
    zombie_details = []

    if not pids and category == "zombies":
        ps = subprocess.run(["ps", "-eo", "pid,ppid,stat,comm"], capture_output=True, text=True, timeout=10)
        pids = []
        for line in ps.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3 and "Z" in parts[2]:
                try:
                    zpid = int(parts[0])
                    ppid = int(parts[1]) if len(parts) > 1 else 0
                    pids.append(zpid)
                    zombie_details.append({"pid": zpid, "ppid": ppid, "comm": parts[3] if len(parts) > 3 else "?"})
                except ValueError:
                    pass

    if not pids:
        return {"cleaned": 0, "zombies_found": len(zombie_details), "message": "无进程需要清理", "details": zombie_details[:10]}

    cleaned = []
    errors = []
    for i, pid in enumerate(pids):
        try:
            detail = zombie_details[i] if i < len(zombie_details) else {}
            ppid = detail.get("ppid", 0)

            # 僵尸进程无法直接 kill —— 尝试向父进程发 SIGCHLD 让其 wait()
            if ppid and ppid > 1:
                try:
                    os.kill(ppid, signal.SIGCHLD)
                except (ProcessLookupError, PermissionError):
                    pass

            # 再尝试 SIGKILL 僵尸本身（通常无效但无害）
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

            cleaned.append({"pid": pid, "ppid": ppid, "method": "SIGCHLD→parent + SIGKILL"})

        except Exception as e:
            errors.append({"pid": pid, "error": str(e)})

    remaining = 0
    try:
        ps2 = subprocess.run(["ps", "-eo", "pid,stat"], capture_output=True, text=True, timeout=5)
        remaining = sum(1 for line in ps2.stdout.splitlines() if " Z " in line or line.endswith(" Z"))
    except Exception:
        pass

    return {
        "cleaned": len(cleaned), "attempted": len(pids),
        "zombies_remaining": remaining, "details": zombie_details[:10], "errors": errors,
        "note": "僵尸进程由父进程回收。如果父进程(PID>1的PPID)不调用wait(),僵尸将持续存在。重启父进程或系统可彻底清除。" if remaining > 0 else "清理完成",
    }


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
    """多核 CPU 压测 — 结构化分析 + Trace 记录 + 告警推送."""
    if duration > 120:
        raise HTTPException(400, "最长压测 120 秒")

    import re as _re
    import time as _time

    cores = cores or os.cpu_count() or 1
    trace_id = f"stress-{int(_time.time()*1000)}"

    # ---- 压测前快照 ----
    before_snap = _collect_perf_snapshot()
    before_load = before_snap["load_avg"]

    # ---- 执行压测 ----
    t0 = _time.time()
    script_path = "/home/oy0/security-agent/scripts/stress_cpu.sh"
    stdout_raw = ""
    stress_ok = False

    if os.path.exists(script_path):
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", script_path, "--multi", "--duration", str(duration),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_raw, stderr_raw = await asyncio.wait_for(proc.communicate(), timeout=duration + 30)
            stdout_raw = stdout_raw.decode() if isinstance(stdout_raw, bytes) else stdout_raw
            stderr_raw = stderr_raw.decode() if isinstance(stderr_raw, bytes) else stderr_raw
            stress_ok = True
        except asyncio.TimeoutError:
            stress_ok = False
            stderr_raw = "压测超时"
    else:
        import multiprocessing as _mp
        def _burn(end_t: float):
            while _time.time() < end_t:
                _ = sum(i * i for i in range(10000))
        end_t = _time.time() + duration
        procs = []
        for _ in range(cores):
            p = _mp.Process(target=_burn, args=(end_t,))
            p.start()
            procs.append(p)
        for p in procs:
            p.join(timeout=duration + 5)
            if p.is_alive():
                p.terminate()
        stress_ok = True
        stderr_raw = ""

    elapsed = _time.time() - t0

    # 清洗 ANSI 转义码
    stdout_clean = _re.sub(r'\x1b\[[0-9;]*m', '', (stdout_raw or "")).strip()
    stderr_clean = _re.sub(r'\x1b\[[0-9;]*m', '', (stderr_raw or "")).strip()
    # 只保留关键行（跳过分隔线和 INFO 前缀）
    key_lines = [l for l in stdout_clean.split("\n") if l.strip() and "INFO" not in l[:10] and "===" not in l[:5]]
    stdout_clean = "\n".join(key_lines[:10])

    # ---- 压测后快照 ----
    after_snap = _collect_perf_snapshot()
    after_load = after_snap["load_avg"]

    # ---- 对比分析 ----
    load_delta = round(after_load[0] - before_load[0], 2)
    cpu_avg = after_snap.get("avg_cpu_percent", 0)
    stress_pct = round(cpu_avg / (cores * 100) * 100, 1) if cores > 0 else 0

    # 负载级别判定
    if after_load[0] <= cores * 0.5:
        load_level, level_color = "轻载", "success"
    elif after_load[0] <= cores * 0.8:
        load_level, level_color = "中载", "warning"
    elif after_load[0] <= cores * 1.5:
        load_level, level_color = "高载", "danger"
    else:
        load_level, level_color = "过载", "danger"

    # 瓶颈检测
    bottlenecks = []
    if after_snap.get("avg_cpu_percent", 0) > 85:
        bottlenecks.append("CPU 接近瓶颈 (>85%)")
    if after_load[0] > cores * 1.5:
        bottlenecks.append(f"负载过高: {after_load[0]:.1f} vs {cores}核心 (理想≤{cores*1.0:.1f})")
    if after_snap.get("zombies", 0) > 0:
        bottlenecks.append(f"存在 {after_snap['zombies']} 个僵尸进程")
    if after_snap.get("memory_percent", 0) > 90:
        bottlenecks.append(f"内存使用率过高: {after_snap['memory_percent']}%")

    summary = (
        f"{cores}核 × {duration}秒 | "
        f"负载 {before_load[0]:.1f} → {after_load[0]:.1f} (Δ{load_delta:+.1f}) | "
        f"平均CPU {cpu_avg:.1f}% | {load_level}"
    )

    # ---- Trace 记录 (写入审计日志) ----
    from security_agent.audit import log as audit_log
    audit_log.append_audit("cpu_stress", {
        "trace_id": trace_id,
        "duration": round(elapsed, 1), "cores": cores,
        "load_before": before_load[0], "load_after": after_load[0],
        "load_level": load_level, "bottlenecks": bottlenecks,
        "summary": summary,
    })

    # ---- 发布告警 (写入 data/alerts/ 持久化) ----
    try:
        from security_agent.notify.alerts import publish_monitor_event
        publish_monitor_event({
            "ts": _time.strftime("%Y-%m-%dT%H:%M:%S"),
            "type": "CPU 压测完成",
            "level": "高" if load_level in ("高载","过载") else "中",
            "message": summary,
            "trace_id": trace_id,
            "cpu_after": after_load[0],
            "load_level": load_level,
            "bottlenecks": bottlenecks,
        })
    except Exception:
        pass

    return {
        "status": "completed" if stress_ok else "timeout",
        "duration": round(elapsed, 1),
        "cores": cores,
        "trace_id": trace_id,
        "analysis": {
            "level": load_level,
            "level_color": level_color,
            "stress_percent": stress_pct,
            "load_delta": load_delta,
            "bottlenecks": bottlenecks,
            "summary": summary,
        },
        "before": before_snap,
        "after": after_snap,
        "per_core": after_snap.get("per_core", []),
        "output": stdout_clean[:2000] if stdout_clean else f"{cores}核 × {duration}秒 压测完成",
        "errors": stderr_clean[-500:] if stderr_clean else None,
    }


def _collect_perf_snapshot() -> dict:
    """采集当前性能快照."""
    import psutil as _ps
    try:
        cpu_pct = _ps.cpu_percent(interval=0.5, percpu=True)
        mem = _ps.virtual_memory()
        disk = _ps.disk_usage("/")
        load = list(_ps.getloadavg())
        zombies = 0
        try:
            for p in _ps.process_iter(["status"]):
                if p.info["status"] == "zombie":
                    zombies += 1
        except Exception:
            pass
        return {
            "load_avg": [round(load[0], 2), round(load[1], 2), round(load[2], 2)],
            "avg_cpu_percent": round(sum(cpu_pct) / len(cpu_pct), 1) if cpu_pct else 0,
            "per_core": [round(c, 1) for c in cpu_pct],
            "memory_percent": round(mem.percent, 1),
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "disk_percent": round(disk.percent, 1),
            "process_count": len(_ps.pids()),
            "zombies": zombies,
        }
    except Exception as e:
        return {"error": str(e)}


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


# ============================================================
# 任务分发 API — 权限管控 + 沙箱预演
# ============================================================

from security_agent.api.deps import get_current_user, require_operator
from security_agent.auth.models import User
from security_agent.ops.task_dispatch import (
    dispatch,
    list_all_tasks,
    get_task,
    TASK_CATALOG,
)


@router.get("/tasks")
async def list_ops_tasks(user: User = Depends(get_current_user)):
    """列出当前角色可执行的所有运维任务."""
    tasks = list_all_tasks(user.role)
    return {"total": len(tasks), "user_role": user.role, "tasks": tasks}


@router.get("/tasks/{task_name}")
async def task_detail(task_name: str, user: User = Depends(get_current_user)):
    """获取任务详情."""
    t = get_task(task_name)
    if not t:
        raise HTTPException(404, detail=f"任务不存在: {task_name}")
    return t


@router.post("/dispatch")
async def dispatch_task(
    body: dict,
    user: User = Depends(get_current_user),
):
    """权限管控 + 任务分发.

    Body: { task_name, mode? (direct/preview/sandbox), task_args? }
    """
    task_name = body.get("task_name", "")
    mode = body.get("mode", "direct")
    task_args = body.get("task_args", {}) or {}

    if not task_name:
        raise HTTPException(400, detail="task_name 缺失")
    if task_name not in TASK_CATALOG:
        raise HTTPException(400, detail=f"未知任务: {task_name}")
    if mode not in ("direct", "preview", "sandbox"):
        raise HTTPException(400, detail=f"未知模式: {mode}")

    if mode == "sandbox":
        pass  # 沙箱模式对 readonly 开放
    else:
        required_role = TASK_CATALOG[task_name].min_role
        from security_agent.ops.task_dispatch import ROLE_LEVEL
        if ROLE_LEVEL.get(user.role, -1) < ROLE_LEVEL.get(required_role, 99):
            raise HTTPException(
                403,
                detail=f"权限不足: {user.role} 无法执行 {task_name} (需要 {required_role})",
            )

    result = await dispatch(
        task_name, user=user.username, role=user.role, mode=mode, task_args=task_args,
    )
    return result.to_dict()
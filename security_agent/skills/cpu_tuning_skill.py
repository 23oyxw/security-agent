"""CPU 调优与压测 Skill — 一键加速、多核压测、阈值监控、安全停止."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from security_agent.audit import log as audit
from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.timeutil import now_iso


# ---- 全局压测追踪 ----
_stress_registry: dict[str, Any] = {
    "procs": [],
    "started_at": 0.0,
    "mode": "",
    "cpu_count": 0,
    "timeout": 0,
    "threshold": 0.0,
    "monitoring": False,
    "stop_requested": False,
}
_stress_lock = threading.Lock()


def _run(cmd: str, timeout: float = 30) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


# ═══════════════════════════════════════════════════════════
# CPU 加速 / 调优
# ═══════════════════════════════════════════════════════════

def _detect_governor_driver() -> str | None:
    """检测 CPU governor 驱动类型."""
    rc, out, _ = _run("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null")
    if rc == 0 and out.strip():
        return out.strip()
    return None


def _get_current_governor(cpu: int = 0) -> str:
    rc, out, _ = _run(f"cat /sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor 2>/dev/null")
    if rc == 0:
        return out.strip()
    return "unknown"


def _get_cpu_freq(cpu: int = 0) -> dict[str, int]:
    try:
        base = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq"
        cur = int(Path(f"{base}/scaling_cur_freq").read_text().strip())
        min_f = int(Path(f"{base}/scaling_min_freq").read_text().strip())
        max_f = int(Path(f"{base}/scaling_max_freq").read_text().strip())
        return {"current_khz": cur, "min_khz": min_f, "max_khz": max_f}
    except (FileNotFoundError, ValueError, PermissionError):
        return {"current_khz": 0, "min_khz": 0, "max_khz": 0}


def set_performance_governor() -> dict[str, Any]:
    """切换到 performance 模式 — 所有核心锁最高频."""
    available = _detect_governor_driver()
    if available is None:
        return {"ok": False, "error": "系统不支持 CPU governor 切换（非标准 cpufreq 驱动）", "governors_available": None}

    available_list = available.split()
    if "performance" not in available_list:
        return {"ok": False, "error": f"当前内核未编译 performance governor", "governors_available": available_list}

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    cpu_count = os.cpu_count() or 1

    for cpu in range(cpu_count):
        gov_path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"
        try:
            with open(gov_path, "w") as f:
                f.write("performance")
            results.append({"cpu": cpu, "governor": "performance", "ok": True})
        except PermissionError:
            errors.append(f"cpu{cpu}: 需要 root 权限写入 {gov_path}")
        except FileNotFoundError:
            errors.append(f"cpu{cpu}: cpufreq 不可用")
        except Exception as e:
            errors.append(f"cpu{cpu}: {e}")

    succeeded = sum(1 for r in results if r.get("ok"))
    return {
        "ok": succeeded > 0,
        "governor": "performance",
        "total_cpus": cpu_count,
        "succeeded": succeeded,
        "failed": cpu_count - succeeded,
        "results": results,
        "errors": errors if errors else None,
        "requires_root": any("root" in e for e in errors),
        "message": (
            f"已切换 {succeeded}/{cpu_count} 个核心到 performance"
            if succeeded > 0
            else "需要 root 权限: sudo python -c '...'"
            if any("root" in e for e in errors)
            else "无法切换 governor"
        ),
    }


def set_powersave_governor() -> dict[str, Any]:
    """恢复到 powersave/ondemand 模式."""
    available = _detect_governor_driver()

    # 选择可用的省电模式
    prefer = ["ondemand", "powersave", "schedutil", "conservative"]
    chosen = None
    if available:
        available_list = available.split()
        for g in prefer:
            if g in available_list:
                chosen = g
                break
    if chosen is None and available:
        chosen = available_list[0]  # 回退第一个

    if chosen is None:
        return {"ok": False, "error": "无法确定可用的省电 governor"}

    cpu_count = os.cpu_count() or 1
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for cpu in range(cpu_count):
        gov_path = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"
        try:
            with open(gov_path, "w") as f:
                f.write(chosen)
            results.append({"cpu": cpu, "governor": chosen, "ok": True})
        except Exception as e:
            errors.append(f"cpu{cpu}: {e}")

    succeeded = sum(1 for r in results if r.get("ok"))
    return {
        "ok": succeeded > 0,
        "governor": chosen,
        "total_cpus": cpu_count,
        "succeeded": succeeded,
        "failed": cpu_count - succeeded,
        "errors": errors if errors else None,
        "message": f"已恢复 {succeeded}/{cpu_count} 核心到 {chosen}",
    }


def get_cpu_status() -> dict[str, Any]:
    """获取完整 CPU 状态."""
    import psutil

    cpu_count = os.cpu_count() or 1
    cpu_percent = psutil.cpu_percent(interval=0.3)
    per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

    # governor
    governor = _get_current_governor(0)

    # frequency
    freq = _get_cpu_freq(0)

    # load
    try:
        load_1m, load_5m, load_15m = os.getloadavg()
    except (AttributeError, OSError):
        load_1m = load_5m = load_15m = 0.0

    # temperature (if available)
    temp = _get_cpu_temp()

    # 进程数
    proc_count = len(list(psutil.process_iter()))

    # 是否在压测中
    is_stressing = bool(_stress_registry["procs"])
    stress_procs_alive = sum(1 for p in _stress_registry["procs"] if p.poll() is None)

    return {
        "cpu_count": cpu_count,
        "cpu_percent": round(cpu_percent, 1),
        "per_cpu": [round(x, 1) for x in per_cpu],
        "governor": governor,
        "frequency_khz": freq["current_khz"],
        "frequency_max_khz": freq["max_khz"],
        "frequency_min_khz": freq["min_khz"],
        "frequency_mhz": round(freq["current_khz"] / 1000, 0) if freq["current_khz"] else 0,
        "load_1m": round(load_1m, 2),
        "load_5m": round(load_5m, 2),
        "load_15m": round(load_15m, 2),
        "load_ratio": round(load_1m / cpu_count, 2) if cpu_count > 0 else 0,
        "temperature": temp,
        "process_count": proc_count,
        "stress_active": is_stressing,
        "stress_procs_alive": stress_procs_alive,
        "stress_mode": _stress_registry["mode"],  # 空串表示未在压测
        "is_optimized": governor == "performance",
        "timestamp": int(time.time()),
    }


def _get_cpu_temp() -> float | None:
    """读取 CPU 温度."""
    paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/hwmon/hwmon0/temp1_input",
        "/sys/class/hwmon/hwmon1/temp1_input",
    ]
    for p in paths:
        try:
            val = int(Path(p).read_text().strip())
            # 毫度 → 度
            if val > 1000:
                return round(val / 1000, 1)
            return round(val, 1)
        except (FileNotFoundError, ValueError, PermissionError):
            continue
    return None


# ═══════════════════════════════════════════════════════════
# CPU 压测
# ═══════════════════════════════════════════════════════════

def start_cpu_stress(
    mode: str = "single",
    duration: int = 30,
    threshold: float = 85.0,
    cpu_count: int | None = None,
) -> dict[str, Any]:
    """启动 CPU 压测（非阻塞）, 支持阈值自动停止.

    Args:
        mode: single | multi | full
        duration: 最大压测时长（秒）
        threshold: CPU 使用率阈值（%），超过自动停止
        cpu_count: 使用的核心数（multi 模式，默认全部）
    """
    with _stress_lock:
        # 先停止已存在的压测
        _kill_all_stress()
        _stress_registry["stop_requested"] = False

    cpu_total = os.cpu_count() or 1
    if mode == "single":
        workers = 1
    elif mode == "full":
        # 比核心数多几个造成更显著压力
        workers = cpu_total + 2
    else:
        workers = cpu_count if cpu_count is not None else cpu_total

    # 检测可用工具
    use_stress = shutil.which("stress") is not None
    use_stress_ng = shutil.which("stress-ng") is not None

    procs: list[subprocess.Popen] = []
    tool = "dd"

    try:
        if use_stress:
            # stress --cpu N --timeout T
            tool = "stress"
            proc = subprocess.Popen(
                ["stress", "--cpu", str(workers)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            procs.append(proc)
        else:
            # fallback: dd 多进程
            for _ in range(workers):
                proc = subprocess.Popen(
                    ["dd", "if=/dev/zero", "of=/dev/null", "bs=1M"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                procs.append(proc)
    except FileNotFoundError:
        # 如果连 dd 都没有（极端情况）
        _kill_all_stress()
        return {"ok": False, "error": "系统中未找到 stress 或 dd 命令，无法压测"}

    with _stress_lock:
        _stress_registry["procs"] = procs
        _stress_registry["started_at"] = time.monotonic()
        _stress_registry["mode"] = mode
        _stress_registry["cpu_count"] = workers
        _stress_registry["timeout"] = duration
        _stress_registry["threshold"] = threshold
        _stress_registry["monitoring"] = True

    # 启动后台监控线程
    monitor_thread = threading.Thread(
        target=_monitor_stress,
        args=(duration, threshold),
        daemon=True,
    )
    monitor_thread.start()

    audit.append_audit(
        "cpu_stress_start",
        {"mode": mode, "workers": workers, "tool": tool, "timeout": duration, "threshold": threshold},
        level="info",
    )

    return {
        "ok": True,
        "mode": mode,
        "tool": tool,
        "workers": workers,
        "max_duration_sec": duration,
        "threshold_pct": threshold,
        "cpu_total": cpu_total,
        "message": f"已启动 {workers} 核压测（{tool}），最长 {duration} 秒，CPU≥{threshold}% 自动停止",
    }


def _monitor_stress(max_duration: int, threshold: float) -> None:
    """后台线程：监控 CPU 并自动停止."""
    import psutil

    start = time.monotonic()
    check_interval = 1.0  # 每秒检查一次

    try:
        while True:
            elapsed = time.monotonic() - start

            # 超时检查
            if elapsed >= max_duration:
                break

            # 手动停止检查
            if _stress_registry["stop_requested"]:
                break

            # 检查进程是否还活着
            if not any(p.poll() is None for p in _stress_registry["procs"]):
                break

            # 阈值检查
            try:
                cpu_val = psutil.cpu_percent(interval=0.5)
                if cpu_val >= threshold:
                    break
            except Exception:
                pass

            time.sleep(check_interval)
    finally:
        _stop_and_report(elapsed, threshold)


def _stop_and_report(elapsed: float, threshold: float) -> None:
    """停止压测并生成报告."""
    import psutil

    with _stress_lock:
        _stress_registry["monitoring"] = False

    cpu_after = psutil.cpu_percent(interval=0.5)
    killed = _kill_all_stress()

    # 等待 CPU 回落
    time.sleep(1.5)
    cpu_cooled = psutil.cpu_percent(interval=0.3)

    stop_reason = "manual"
    if elapsed >= _stress_registry["timeout"]:
        stop_reason = "timeout"
    elif cpu_after >= threshold:
        stop_reason = "threshold"

    audit.append_audit(
        "cpu_stress_stop",
        {
            "stop_reason": stop_reason,
            "duration_sec": round(elapsed, 1),
            "cpu_after": round(cpu_after, 1),
            "cpu_cooled": round(cpu_cooled, 1),
            "killed_pids": killed,
        },
        level="info",
    )


def stop_cpu_stress() -> dict[str, Any]:
    """手动停止压测."""
    with _stress_lock:
        _stress_registry["stop_requested"] = True

    killed = _kill_all_stress()
    return {
        "ok": True,
        "killed_pids": killed,
        "message": f"已停止 {len(killed)} 个压测进程" if killed else "无压测进程在运行",
    }


def _kill_all_stress() -> list[int]:
    """杀死所有压测进程."""
    killed: list[int] = []
    for proc in _stress_registry["procs"]:
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
            killed.append(proc.pid)
    _stress_registry["procs"] = []
    _stress_registry["monitoring"] = False

    # 系统级兜底
    try:
        subprocess.run(
            ["bash", "-c", "pkill -f 'dd if=/dev/zero' 2>/dev/null; pkill -f '^stress' 2>/dev/null"],
            timeout=3,
        )
    except Exception:
        pass

    return killed


def _kill_stress_handlers(signum, frame):
    """信号处理器 — 确保进程退出时清理."""
    _kill_all_stress()


signal.signal(signal.SIGTERM, _kill_stress_handlers)
signal.signal(signal.SIGINT, _kill_stress_handlers)


# ═══════════════════════════════════════════════════════════
# Skill 定义
# ═══════════════════════════════════════════════════════════

class CpuTuningSkill(SkillBase):
    """CPU 调优与压测 Skill."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="cpu_tuning",
            display_name="CPU 调优",
            description="CPU 一键加速（performance governor）、多核压测（阈值自动停止）、一键停止、实时状态",
            version="1.0.0",
            tags=("cpu", "performance", "stress", "tuning", "optimization"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="cpu_status",
                description="获取 CPU 完整状态: 使用率、频率、governor、温度、负载、压测状态",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_status,
                auto_ok=True,
            ),
            ToolDef(
                name="cpu_turbo_on",
                description="CPU 一键加速: 所有核心切换到 performance governor（需要 root 权限）",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_turbo_on,
                auto_ok=False,
            ),
            ToolDef(
                name="cpu_turbo_off",
                description="CPU 恢复省电模式: 切换回 ondemand/powersave governor",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_turbo_off,
                auto_ok=True,
            ),
            ToolDef(
                name="cpu_stress_start",
                description=(
                    "启动 CPU 多核压测。mode: single(单核), multi(全核), full(全核+2)。"
                    "threshold 为自动停止阈值(%)，达到后自动停止。duration 为最大时长(秒)。"
                    "压测在后台运行，可用 cpu_stress_stop 手动停止或 cpu_status 查看状态。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "description": "压测模式: single/multi/full",
                            "enum": ["single", "multi", "full"],
                            "default": "multi",
                        },
                        "duration": {
                            "type": "integer",
                            "description": "最大压测时长（秒），默认 60",
                            "default": 60,
                        },
                        "threshold": {
                            "type": "number",
                            "description": "CPU 使用率自动停止阈值（%），默认 85.0。超过此值自动停止",
                            "default": 85.0,
                        },
                    },
                    "required": [],
                },
                handler=self._tool_stress_start,
                auto_ok=False,
            ),
            ToolDef(
                name="cpu_stress_stop",
                description="一键停止 CPU 压测 — 立即杀掉所有压测进程",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_stress_stop,
                auto_ok=True,
            ),
        ]

    # ---- 工具处理器 ----

    async def _tool_status(self) -> str:
        return json.dumps(get_cpu_status(), ensure_ascii=False, indent=2)

    async def _tool_turbo_on(self) -> str:
        result = set_performance_governor()
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_turbo_off(self) -> str:
        result = set_powersave_governor()
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_stress_start(
        self,
        mode: str = "multi",
        duration: int = 60,
        threshold: float = 85.0,
    ) -> str:
        result = start_cpu_stress(
            mode=mode,
            duration=min(duration, 300),  # 最长 5 分钟
            threshold=threshold,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_stress_stop(self) -> str:
        result = stop_cpu_stress()
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ---- 告警回调 ----

    async def on_alert(self, event: dict[str, Any]) -> dict[str, Any] | None:
        etype = str(event.get("type", ""))
        if "CPU" not in etype:
            return None
        status = get_cpu_status()
        return {
            "action": "cpu_diag",
            "cpu_status": status,
            "recommendation": (
                "建议排查高 CPU 进程: ps aux --sort=-%cpu | head -20"
                if status["cpu_percent"] > 50
                else "CPU 指标正常，无需干预"
            ),
        }


# Skill 自动发现入口
skill_instance = CpuTuningSkill()

"""风险演练编排 — 诱饵启停、场景运行、扫描合并、CPU 压测."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.audit import log as audit
from security_agent.demo.boundary import run_terminal_boundary_tests, summarize_boundary
from security_agent.demo.evaluator import list_fixture_catalog, run_detection_calibration
from security_agent.demo.fixture_catalog import FIXTURE_CATEGORIES, DETECTION_FIXTURES
from security_agent.demo.scenarios import (
    SCENARIO_META,
    risks_to_cube_points,
    synthetic_risks,
)
from security_agent.monitor.service import get_monitor_service
from security_agent.scanner import engine as scanner
from security_agent.timeutil import now_iso

_DECOY_SCRIPT = Path(__file__).resolve().parent / "decoy.py"
_demo_singleton: "DemoService | None" = None

_STRESS_TIMEOUT = 60  # 压测最多跑 60 秒（timeout 兜底）
_STRESS_WARMUP = 8   # 启动后等 8 秒等 CPU 爬升


class DemoService:
    def __init__(self) -> None:
        self._decoys: list[subprocess.Popen[Any]] = []
        self._stress_procs: list[subprocess.Popen[Any]] = []
        self._stress_start: float = 0.0
        self._stress_expired: bool = False

    # ── 原有诱饵方法 ──────────────────────────────────────────────

    def list_scenarios(self) -> list[dict[str, str]]:
        return [{"id": k, **v} for k, v in SCENARIO_META.items()]

    def list_fixture_categories(self) -> dict[str, str]:
        return dict(FIXTURE_CATEGORIES)

    def run_fixture_calibration(self, category: str | None = None) -> dict[str, Any]:
        out = run_detection_calibration(category=category or "all")
        audit.append_audit(
            "demo_calibration",
            {
                "accuracy": out["summary"]["accuracy_pct"],
                "failed": out["summary"]["failed"],
                "total": out["summary"]["total"],
            },
            level="info",
        )
        return out

    def get_fixture_catalog(self) -> dict[str, Any]:
        return list_fixture_catalog()

    def start_decoy(self, simulate_tool: str = "nmap") -> dict[str, Any]:
        if simulate_tool not in config.HIGH_RISK_PROCESS_NAMES:
            simulate_tool = "nmap"
        proc = subprocess.Popen(
            [
                config.python_executable(),
                str(_DECOY_SCRIPT),
                "--hold",
                "--simulate-tool",
                simulate_tool,
            ],
            cwd=str(config.PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._decoys.append(proc)
        audit.append_audit(
            "demo_decoy_start",
            {"pid": proc.pid, "simulate_tool": simulate_tool},
            level="info",
        )
        return {
            "ok": True,
            "pid": proc.pid,
            "simulate_tool": simulate_tool,
            "message": f"已启动诱饵进程 PID={proc.pid}（仅 sleep，命令行含 {simulate_tool}）",
        }

    def stop_decoys(self) -> dict[str, Any]:
        stopped: list[int] = []
        for proc in self._decoys:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            if proc.pid:
                stopped.append(proc.pid)
        self._decoys.clear()
        audit.append_audit("demo_decoy_stop", {"pids": stopped}, level="info")
        return {"ok": True, "stopped_pids": stopped, "message": f"已停止 {len(stopped)} 个诱饵进程"}

    # ── CPU 压测 ──────────────────────────────────────────────────

    def is_stressing(self) -> bool:
        """是否有压测进程正在运行."""
        if self._stress_expired:
            return False
        self._prune_stress_procs()
        return bool(self._stress_procs)

    def _prune_stress_procs(self) -> None:
        """移除已退出的压测进程."""
        self._stress_procs = [p for p in self._stress_procs if p.poll() is None]

    def _kill_stress_procs(self) -> list[int]:
        """强制杀光所有压测进程."""
        killed: list[int] = []
        for proc in self._stress_procs:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            if proc.pid:
                killed.append(proc.pid)
        self._stress_procs.clear()
        self._stress_expired = False
        return killed

    def run_cpu_stress(self) -> dict[str, Any]:
        """
        后台压 CPU → 等待爬升 → 采集监控告警 → 返回结果（自动停止）。

        安全设计（三重保险）：
        1. timeout 60s 硬限制：dd 被自动杀死
        2. UI 提供「停止压测」按钮
        3. 终端兜底：bash scripts/cleanup_stress.sh
        """
        # 压测前清理
        self._kill_stress_procs()
        self._stress_expired = False

        # 1. 记录压测前 CPU
        try:
            import psutil
            cpu_before = psutil.cpu_percent(interval=0.3)
        except Exception:
            cpu_before = 0.0

        # 2. 采集压测前的监控告警基线
        monitor_svc = get_monitor_service()
        before_events = set()
        try:
            recent = monitor_svc.get_events(limit=200)
            before_events = {
                e.get("ts", "") + "|" + e.get("type", "") + "|" + e.get("message", "")
                for e in recent
            }
        except Exception:
            pass

        # 3. 启动 dd 压测（timeout 60s 硬限制）
        try:
            proc = subprocess.Popen(
                ["timeout", str(_STRESS_TIMEOUT), "dd", "if=/dev/zero", "of=/dev/null", "bs=1M"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return {
                "ok": False,
                "error": "系统中未找到 timeout 或 dd 命令，无法进行 CPU 压测",
                "cpu_before": cpu_before,
            }
        self._stress_procs.append(proc)
        self._stress_start = time.monotonic()

        # 后台线程：超时自动清理
        def _auto_cleanup(pid: int) -> None:
            time.sleep(_STRESS_TIMEOUT + 3)
            self._prune_stress_procs()
            if not self._stress_procs:
                self._stress_expired = True

        threading.Thread(target=_auto_cleanup, args=(proc.pid,), daemon=True).start()

        # 4. 等待 CPU 爬升
        time.sleep(_STRESS_WARMUP)

        # 5. 采集压测中 CPU
        try:
            cpu_during = psutil.cpu_percent(interval=0.5)
            cpu_peak = max(cpu_before, cpu_during)
            # 多采几次取最高
            for _ in range(4):
                cpu_val = psutil.cpu_percent(interval=0.3)
                if cpu_val > cpu_peak:
                    cpu_peak = cpu_val
        except Exception:
            cpu_during = 0.0
            cpu_peak = 0.0

        # 6. 采集监控告警（过滤出压测期间新增的）
        alarms: list[dict[str, Any]] = []
        try:
            recent = monitor_svc.get_events(limit=200)
            for e in recent:
                key = e.get("ts", "") + "|" + e.get("type", "") + "|" + e.get("message", "")
                if key not in before_events and e.get("type") in ("CPU 占用过高",):
                    alarms.append(e)
        except Exception:
            pass

        # 7. 自动停止压测（避免一直耗 CPU）
        self.stop_cpu_stress()

        return {
            "ok": True,
            "stress_pid": proc.pid,
            "cpu_before": round(cpu_before, 1),
            "cpu_during": round(cpu_during, 1),
            "cpu_peak": round(cpu_peak, 1),
            "alarm_count": len(alarms),
            "alarms": alarms[:20],
            "threshold": getattr(monitor_svc, "cpu_threshold", 80.0),
            "threshold_triggered": cpu_peak > getattr(monitor_svc, "cpu_threshold", 80.0),
            "message": (
                f"CPU {cpu_before:.0f}% → {cpu_peak:.0f}% (阈值 {getattr(monitor_svc, 'cpu_threshold', 80):.0f}%) · "
                f"触发告警 {len(alarms)} 条"
            ),
        }

    def stop_cpu_stress(self) -> dict[str, Any]:
        """停止压测进程."""
        killed = self._kill_stress_procs()
        audit.append_audit("demo_cpu_stress_stop", {"killed_pids": killed}, level="info")
        return {"ok": True, "killed_pids": killed, "message": f"已停止 {len(killed)} 个压测进程"}

    # ── 统一清理 ──────────────────────────────────────────────────

    def cleanup(self) -> dict[str, Any]:
        """清理所有诱饵 + 压测进程."""
        decoy_r = self.stop_decoys()
        stress_r = self.stop_cpu_stress()
        return {
            "ok": True,
            "decoys_stopped": decoy_r["stopped_pids"],
            "stress_killed": stress_r["killed_pids"],
            "message": f"诱饵 {len(decoy_r['stopped_pids'])} · 压测 {len(stress_r['killed_pids'])}",
        }

    # ── 原有扫描 / 边界方法 ───────────────────────────────────────

    def run_boundary_tests(self) -> dict[str, Any]:
        rows = run_terminal_boundary_tests()
        summary = summarize_boundary(rows)
        audit.append_audit("demo_boundary", summary, level="info")
        return {"cases": rows, "summary": summary}

    def build_synthetic_scan(self) -> dict[str, Any]:
        risks = synthetic_risks()
        return {
            "scanned_at": now_iso(),
            "platform": config.platform_label(),
            "risks": risks,
            "risk_count": len(risks),
            "demo_mode": True,
            "cube_points": risks_to_cube_points(risks),
        }

    def merge_scan(self, *, include_synthetic: bool = True, run_live_scan: bool = True) -> dict[str, Any]:
        live: dict[str, Any] = scanner.run_security_scan() if run_live_scan else {"risks": []}
        merged: list[dict[str, Any]] = []
        for r in live.get("risks", []):
            item = dict(r)
            item.setdefault("source", "live")
            item.setdefault("layer", "检测")
            merged.append(item)
        if include_synthetic:
            merged.extend(synthetic_risks())
        for r in merged:
            if str(r.get("message", "")).startswith("[演练]"):
                continue
            if r.get("source") == "live":
                r["message"] = f"[实盘] {r.get('message', '')}"
        return {
            "scanned_at": now_iso(),
            "platform": config.platform_label(),
            "risks": merged,
            "risk_count": len(merged),
            "live_count": len(live.get("risks", [])),
            "synthetic_count": len(synthetic_risks()) if include_synthetic else 0,
            "demo_mode": True,
            "cube_points": risks_to_cube_points(merged),
        }

    def run_scenario(self, scenario_id: str, *, simulate_tool: str = "nmap") -> dict[str, Any]:
        meta = SCENARIO_META.get(scenario_id)
        if not meta:
            return {"ok": False, "error": f"未知场景: {scenario_id}"}

        result: dict[str, Any] = {
            "ok": True,
            "scenario_id": scenario_id,
            "title": meta["title"],
            "description": meta["desc"],
            "ran_at": now_iso(),
        }

        if scenario_id == "synthetic_mixed":
            result["scan"] = self.build_synthetic_scan()
        elif scenario_id == "live_decoy_process":
            decoy = self.start_decoy(simulate_tool=simulate_tool)
            scan = scanner.run_security_scan()
            live = []
            for r in scan.get("risks", []):
                if r.get("pid") == decoy.get("pid") or simulate_tool in str(r.get("cmdline", "")):
                    item = dict(r)
                    item["source"] = "decoy"
                    item["layer"] = "检测"
                    live.append(item)
            result["decoy"] = decoy
            result["scan"] = {
                **scan,
                "risks": live or scan.get("risks", [])[:5],
                "risk_count": len(live) if live else min(5, scan.get("risk_count", 0)),
                "demo_mode": True,
                "cube_points": risks_to_cube_points(live or scan.get("risks", [])[:5]),
            }
        elif scenario_id == "cpu_stress":
            result["cpu_stress"] = self.run_cpu_stress()
            # 同时注入 CPU 合成风险到立体图
            result["scan"] = self.build_synthetic_scan()
        elif scenario_id == "terminal_boundary":
            result["boundary"] = self.run_boundary_tests()
        elif scenario_id == "full_drill":
            decoy = self.start_decoy(simulate_tool=simulate_tool)
            result["decoy"] = decoy
            result["boundary"] = self.run_boundary_tests()
            result["scan"] = self.merge_scan(include_synthetic=True, run_live_scan=True)
        elif scenario_id == "fixture_calibration":
            result["calibration"] = self.run_fixture_calibration()
            result["boundary"] = self.run_boundary_tests()
            result["fixture_total"] = len(DETECTION_FIXTURES)
        else:
            result["ok"] = False
            result["error"] = "未实现的场景"

        audit.append_audit("demo_scenario", {"id": scenario_id, "ok": result.get("ok")}, level="info")
        return result


def get_demo_service() -> DemoService:
    global _demo_singleton
    if _demo_singleton is None:
        _demo_singleton = DemoService()
    return _demo_singleton
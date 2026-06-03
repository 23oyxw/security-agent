"""Background monitoring — processes and sensitive paths."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from security_agent import config
from security_agent.audit import log as audit
from security_agent.monitor.auth_watch import AuthLogWatcher
from security_agent.monitor.cron_watch import collect_cron_signatures, diff_cron
from security_agent.monitor.listen_watch import diff_listeners, snapshot_listeners
from security_agent.scanner.engine import _match_high_risk_process
from security_agent.notify.alerts import publish_monitor_event
from security_agent.timeutil import now_iso
from security_agent.security.redact import redact_dict, redact_text


@dataclass
class MonitorService:
    interval_sec: float = 5.0
    max_events: int = 500
    log_all_new_processes: bool = True
    cpu_threshold: float = 80.0
    _running: bool = field(default=False, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _events: deque[dict[str, Any]] = field(default_factory=deque, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _known_pids: set[int] = field(default_factory=set, init=False)
    _path_mtimes: dict[str, float] = field(default_factory=dict, init=False)
    _tick_count: int = field(default=0, init=False)
    _last_snapshot: list[dict[str, Any]] = field(default_factory=list, init=False)
    _auth_watcher: AuthLogWatcher = field(default_factory=AuthLogWatcher, init=False)
    _listener_snap: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict, init=False)
    _cron_sigs: dict[str, str] = field(default_factory=dict, init=False)

    def start(self) -> str:
        if self._running:
            return "监控已在运行"
        self._running = True
        self._tick_count = 0
        self._known_pids = {p.pid for p in psutil.process_iter(["pid"])}
        self._path_mtimes = {}
        for path_str in config.SENSITIVE_PATHS:
            p = Path(path_str)
            if p.exists():
                try:
                    self._path_mtimes[path_str] = p.stat().st_mtime
                except OSError:
                    pass
        baseline = len(self._known_pids)
        self._listener_snap = snapshot_listeners()
        self._cron_sigs = collect_cron_signatures()
        self._auth_watcher = AuthLogWatcher()
        self._push(
            {
                "ts": now_iso(),
                "type": "监控启动",
                "level": "信息",
                "message": (
                    f"已建立进程基线 {baseline}；监听端口 {len(self._listener_snap)}；"
                    f"P2: 登录/端口/cron 已启用"
                ),
            }
        )
        self._thread = threading.Thread(target=self._loop, daemon=True, name="sec-monitor")
        self._thread.start()
        audit.append_audit("monitor_start", {"interval": self.interval_sec, "baseline": baseline})
        return "监控已启动"

    def stop(self) -> str:
        if not self._running:
            return "监控未运行"
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval_sec + 2)
            self._thread = None
        self._push(
            {
                "ts": now_iso(),
                "type": "监控停止",
                "level": "信息",
                "message": f"共记录 {len(self._events)} 条事件",
            }
        )
        audit.append_audit("monitor_stop", {})
        return "监控已停止"

    @property
    def running(self) -> bool:
        return self._running

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def known_pid_count(self) -> int:
        return len(self._known_pids)

    def get_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)[-limit:][::-1]

    def get_process_snapshot(self, limit: int = 80) -> list[dict[str, Any]]:
        with self._lock:
            if self._last_snapshot:
                return list(self._last_snapshot)[:limit]
        return self._build_snapshot(limit)

    def _build_snapshot(self, limit: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent"]):
            try:
                info = proc.info
                raw_cmd = " ".join(proc.cmdline()[:15]) if proc.cmdline() else ""
                reason = _match_high_risk_process(info.get("name") or "", raw_cmd)
                cmd = redact_text(raw_cmd)
                rows.append(
                    {
                        "pid": info.get("pid"),
                        "name": info.get("name"),
                        "username": info.get("username"),
                        "cpu_percent": info.get("cpu_percent"),
                        "high_risk": reason is not None,
                        "cmdline": cmd[:120],
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if len(rows) >= limit:
                break
        rows.sort(key=lambda r: (not r["high_risk"], r.get("name") or ""))
        with self._lock:
            self._last_snapshot = rows
        return rows

    def _push(self, event: dict[str, Any]) -> None:
        event = redact_dict(event)
        with self._lock:
            self._events.append(event)
            while len(self._events) > self.max_events:
                self._events.popleft()
        try:
            publish_monitor_event(event)
        except Exception:
            pass  # 告警通道失败不影响监控主流程
        # 升级策略引擎异步处理（不阻塞监控主循环）
        try:
            self._try_escalate(event)
        except Exception:
            pass

    @staticmethod
    def _try_escalate(event: dict[str, Any]) -> None:
        """将事件推送到升级策略引擎（在独立线程中运行 asyncio）."""
        import asyncio
        from security_agent.agent.escalation import get_escalation_engine

        level = str(event.get("level", ""))
        if level not in ("严重", "高"):
            return

        def _run() -> None:
            try:
                asyncio.run(get_escalation_engine().process_event(event))
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True, name="sec-escalate").start()

    def _loop(self) -> None:
        while self._running:
            try:
                self._tick_count += 1
                self._tick_processes()
                self._tick_paths()
                self._tick_p2()
                self._build_snapshot(80)
                self._tick_cpu()
                if self._tick_count % 6 == 0:
                    self._push(
                        {
                            "ts": now_iso(),
                            "type": "心跳",
                            "level": "信息",
                            "message": f"巡检 #{self._tick_count}，已知进程 {len(self._known_pids)}",
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                self._push(
                    {
                        "ts": now_iso(),
                        "type": "监控错误",
                        "message": str(exc),
                        "level": "低",
                    }
                )
            time.sleep(self.interval_sec)

    def _tick_processes(self) -> None:
        current: set[int] = set()
        for proc in psutil.process_iter(["pid", "name", "cmdline", "username"]):
            try:
                info = proc.info
                pid = info["pid"]
                current.add(pid)
                if pid in self._known_pids:
                    continue
                name = info.get("name") or ""
                cmd_parts = info.get("cmdline") or []
                cmdline = " ".join(cmd_parts) if isinstance(cmd_parts, list) else str(cmd_parts)
                reason = _match_high_risk_process(name, cmdline)
                safe_cmd = redact_text(cmdline)
                if reason:
                    self._push(
                        {
                            "ts": now_iso(),
                            "type": "高危新进程",
                            "pid": pid,
                            "name": name,
                            "username": info.get("username"),
                            "message": reason,
                            "cmdline": safe_cmd[:120],
                            "level": "严重",
                        }
                    )
                elif self.log_all_new_processes:
                    self._push(
                        {
                            "ts": now_iso(),
                            "type": "新进程",
                            "pid": pid,
                            "name": name,
                            "username": info.get("username"),
                            "message": safe_cmd[:100] or name,
                            "level": "信息",
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self._known_pids = current

    def _tick_paths(self) -> None:
        for path_str in config.SENSITIVE_PATHS:
            path = Path(path_str)
            if not path.exists():
                continue
            try:
                mtime = path.stat().st_mtime
                prev = self._path_mtimes.get(path_str)
                if prev is not None and mtime > prev:
                    self._path_mtimes[path_str] = mtime
                    self._push(
                        {
                            "ts": now_iso(),
                            "type": "敏感文件变更",
                            "path": path_str,
                            "message": "检测到敏感路径元数据变化",
                            "level": "高",
                        }
                    )
                elif prev is None:
                    self._path_mtimes[path_str] = mtime
            except OSError:
                continue

    def _tick_p2(self) -> None:
        ts = now_iso()
        if config.MONITOR_AUTH_ENABLED:
            for ev in self._auth_watcher.poll():
                ev["ts"] = ts
                self._push(ev)

        if config.MONITOR_LISTEN_ENABLED:
            current = snapshot_listeners()
            for ev in diff_listeners(self._listener_snap, current):
                ev["ts"] = ts
                self._push(ev)
            self._listener_snap = current

        if config.MONITOR_CRON_ENABLED:
            current_cron = collect_cron_signatures()
            for ev in diff_cron(self._cron_sigs, current_cron):
                ev["ts"] = ts
                self._push(ev)
            self._cron_sigs = current_cron

    def _tick_cpu(self) -> None:
        """全局 CPU 阈值检查（AIOps 核心）。超过阈值即发布高等级事件。"""
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            if cpu > self.cpu_threshold:
                self._push(
                    {
                        "ts": now_iso(),
                        "type": "CPU 占用过高",
                        "level": "高",
                        "message": f"系统 CPU 使用率 {cpu:.1f}% 超过阈值 {self.cpu_threshold}%",
                        "cpu_percent": round(cpu, 1),
                    }
                )
        except Exception:
            pass  # 采样失败不影响主监控循环


_service: MonitorService | None = None


def get_monitor_service() -> MonitorService:
    global _service
    if _service is None:
        _service = MonitorService()
    return _service


# 请使用 get_monitor_service() 获取单例，勿直接实例化

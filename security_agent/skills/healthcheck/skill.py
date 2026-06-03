"""健康巡检 Skill — CPU/内存/磁盘/网络监控，异常告警，趋势分析."""

from __future__ import annotations

import json
import os
import socket
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from security_agent import config
from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.timeutil import now_iso, format_display

# ---- 默认阈值 ----
DEFAULT_THRESHOLDS = {
    "cpu_warn": 70.0,
    "cpu_critical": 90.0,
    "memory_warn": 75.0,
    "memory_critical": 90.0,
    "disk_warn": 80.0,
    "disk_critical": 95.0,
    "load_ratio_warn": 2.0,  # load_1m / CPU 核心数
    "load_ratio_critical": 4.0,
    "swap_warn": 50.0,
    "swap_critical": 80.0,
}

# 快照历史（内存中保留最近 N 条）
_MAX_HISTORY = 120  # 约 10 分钟（每 5 秒一次）


@dataclass
class HealthSnapshot:
    """一次健康快照."""

    ts: str
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    swap_percent: float
    load_1m: float
    load_5m: float
    load_15m: float
    load_ratio: float  # load_1m / cpu_count
    network_bytes_sent: int
    network_bytes_recv: int
    network_conns: int
    uptime_hours: float
    alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_used_gb": round(self.memory_used_gb, 2),
            "memory_total_gb": round(self.memory_total_gb, 2),
            "disk_percent": self.disk_percent,
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
            "swap_percent": self.swap_percent,
            "load_1m": self.load_1m,
            "load_5m": self.load_5m,
            "load_15m": self.load_15m,
            "load_ratio": round(self.load_ratio, 2),
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_recv": self.network_bytes_recv,
            "network_conns": self.network_conns,
            "uptime_hours": round(self.uptime_hours, 1),
            "alerts": self.alerts,
        }


def _load_thresholds() -> dict[str, float]:
    """加载阈值配置，支持环境变量覆盖."""
    t = dict(DEFAULT_THRESHOLDS)
    for key in t:
        env_val = os.getenv(f"HEALTH_{key.upper()}")
        if env_val:
            try:
                t[key] = float(env_val)
            except ValueError:
                pass
    return t


def _bytes_to_gb(b: int) -> float:
    return b / (1024**3)


class HealthCheckSkill(SkillBase):
    """健康巡检 Skill — 系统资源监控、趋势分析、阈值告警."""

    def __init__(self) -> None:
        self._history: deque[HealthSnapshot] = deque(maxlen=_MAX_HISTORY)
        self._thresholds = _load_thresholds()

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="healthcheck",
            display_name="健康巡检",
            description="CPU/内存/磁盘/网络监控，异常告警，趋势分析，定期巡检报告",
            version="1.0.0",
            tags=("monitoring", "health", "alerting", "trend"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="health_full_check",
                description="全面健康巡检：CPU/内存/磁盘/网络/负载/运行时间，返回结构化结果与告警",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_full_check,
            ),
            ToolDef(
                name="health_trend",
                description="获取最近健康趋势（CPU/内存/磁盘变化），含趋势方向与预测",
                parameters={
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "description": "指标名: cpu|memory|disk|all",
                            "default": "all",
                        },
                        "last_n": {
                            "type": "integer",
                            "description": "取最近 N 个快照",
                            "default": 20,
                        },
                    },
                    "required": [],
                },
                handler=self._tool_trend,
            ),
            ToolDef(
                name="health_threshold_check",
                description="检查当前系统资源是否超过告警阈值，返回超限项列表",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_threshold_check,
            ),
            ToolDef(
                name="health_disk_analysis",
                description="磁盘使用分析：各分区使用率、增长预测、大目录扫描",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_disk_analysis,
            ),
            ToolDef(
                name="health_network_analysis",
                description="网络连接分析：连接数、状态分布、异常外连检测",
                parameters={
                    "type": "object",
                    "properties": {
                        "check_exposed": {
                            "type": "boolean",
                            "description": "是否检查高危暴露端口",
                            "default": True,
                        }
                    },
                    "required": [],
                },
                handler=self._tool_network_analysis,
            ),
            ToolDef(
                name="health_get_history",
                description="获取历史健康快照数据（用于趋势图）",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 60},
                    },
                    "required": [],
                },
                handler=self._tool_get_history,
            ),
        ]

    # ---- 核心采集 ----

    def take_snapshot(self) -> HealthSnapshot:
        """采集一次系统健康快照."""
        ts = now_iso()
        alerts: list[str] = []
        th = self._thresholds

        # CPU
        cpu = psutil.cpu_percent(interval=0.3)

        # 内存
        mem = psutil.virtual_memory()
        mem_used_gb = _bytes_to_gb(mem.used)
        mem_total_gb = _bytes_to_gb(mem.total)

        # 磁盘
        disk = psutil.disk_usage("/")
        disk_used_gb = _bytes_to_gb(disk.used)
        disk_total_gb = _bytes_to_gb(disk.total)

        # Swap
        swap = psutil.swap_memory()

        # 负载
        try:
            load_1m, load_5m, load_15m = os.getloadavg()
        except (AttributeError, OSError):
            load_1m = load_5m = load_15m = 0.0
        cpu_count = psutil.cpu_count() or 1
        load_ratio = load_1m / cpu_count

        # 网络
        net = psutil.net_io_counters()
        try:
            net_conns = len(psutil.net_connections(kind="inet"))
        except psutil.AccessDenied:
            net_conns = -1

        # 运行时间
        uptime_sec = time.time() - psutil.boot_time()
        uptime_hours = uptime_sec / 3600

        # 阈值检查
        if cpu >= th["cpu_critical"]:
            alerts.append(f"CPU 使用率 {cpu:.1f}% 超过严重阈值 {th['cpu_critical']}%")
        elif cpu >= th["cpu_warn"]:
            alerts.append(f"CPU 使用率 {cpu:.1f}% 超过告警阈值 {th['cpu_warn']}%")

        if mem.percent >= th["memory_critical"]:
            alerts.append(f"内存使用率 {mem.percent:.1f}% 超过严重阈值 {th['memory_critical']}%")
        elif mem.percent >= th["memory_warn"]:
            alerts.append(f"内存使用率 {mem.percent:.1f}% 超过告警阈值 {th['memory_warn']}%")

        if disk.percent >= th["disk_critical"]:
            alerts.append(f"磁盘使用率 {disk.percent:.1f}% 超过严重阈值 {th['disk_critical']}%")
        elif disk.percent >= th["disk_warn"]:
            alerts.append(f"磁盘使用率 {disk.percent:.1f}% 超过告警阈值 {th['disk_warn']}%")

        if swap.percent >= th["swap_critical"]:
            alerts.append(f"Swap 使用率 {swap.percent:.1f}% 超过严重阈值 {th['swap_critical']}%")
        elif swap.percent >= th["swap_warn"]:
            alerts.append(f"Swap 使用率 {swap.percent:.1f}% 超过告警阈值 {th['swap_warn']}%")

        if load_ratio >= th["load_ratio_critical"]:
            alerts.append(f"负载比 {load_ratio:.1f} 超过严重阈值 {th['load_ratio_critical']}")
        elif load_ratio >= th["load_ratio_warn"]:
            alerts.append(f"负载比 {load_ratio:.1f} 超过告警阈值 {th['load_ratio_warn']}")

        snap = HealthSnapshot(
            ts=ts,
            cpu_percent=cpu,
            memory_percent=mem.percent,
            memory_used_gb=mem_used_gb,
            memory_total_gb=mem_total_gb,
            disk_percent=disk.percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            swap_percent=swap.percent,
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
            load_ratio=load_ratio,
            network_bytes_sent=net.bytes_sent,
            network_bytes_recv=net.bytes_recv,
            network_conns=net_conns,
            uptime_hours=uptime_hours,
            alerts=alerts,
        )
        self._history.append(snap)
        return snap

    # ---- 趋势分析 ----

    def analyze_trend(self, metric: str = "cpu", last_n: int = 20) -> dict[str, Any]:
        """分析指定指标的趋势方向."""
        if len(self._history) < 2:
            return {"metric": metric, "data_points": len(self._history), "trend": "insufficient_data"}

        history = list(self._history)[-last_n:]
        values: list[float] = []
        timestamps: list[str] = []

        for snap in history:
            timestamps.append(snap.ts)
            if metric == "cpu":
                values.append(snap.cpu_percent)
            elif metric == "memory":
                values.append(snap.memory_percent)
            elif metric == "disk":
                values.append(snap.disk_percent)
            elif metric == "load":
                values.append(snap.load_ratio)
            else:
                values.append(snap.cpu_percent)

        if not values:
            return {"metric": metric, "data_points": 0, "trend": "no_data"}

        # 简单线性趋势
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0

        # 趋势判定
        if abs(slope) < 0.1:
            direction = "stable"
        elif slope > 0:
            direction = "rising" if slope < 1.0 else "rapidly_rising"
        else:
            direction = "falling" if slope > -1.0 else "rapidly_falling"

        # 预测（简单线性外推）
        predicted_next = values[-1] + slope
        predicted_next = max(0, min(100, predicted_next))

        return {
            "metric": metric,
            "data_points": n,
            "current": round(values[-1], 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "avg": round(y_mean, 2),
            "slope": round(slope, 4),
            "trend": direction,
            "predicted_next": round(predicted_next, 2),
            "first_ts": timestamps[0],
            "last_ts": timestamps[-1],
            "values": [round(v, 2) for v in values[-30:]],  # 最多返回 30 个点
        }

    # ---- 磁盘分析 ----

    def disk_analysis(self) -> dict[str, Any]:
        """磁盘使用分析."""
        partitions = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(_bytes_to_gb(usage.total), 2),
                    "used_gb": round(_bytes_to_gb(usage.used), 2),
                    "free_gb": round(_bytes_to_gb(usage.free), 2),
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                continue

        # 增长预测（基于历史快照）
        predictions: dict[str, Any] = {}
        if len(self._history) >= 3:
            disk_values = [s.disk_percent for s in self._history]
            n = len(disk_values)
            if n >= 2:
                slope = (disk_values[-1] - disk_values[0]) / (n - 1)
                if slope > 0:
                    # 预测多少小时后磁盘满
                    current = disk_values[-1]
                    remaining = 100 - current
                    if slope > 0:
                        ticks_to_full = remaining / slope
                        hours_to_full = ticks_to_full * 5 / 3600  # 5 秒间隔
                        predictions["hours_until_full"] = round(hours_to_full, 1)
                    predictions["growth_rate_per_hour"] = round(slope * 3600 / 5, 4)

        return {
            "partitions": partitions,
            "predictions": predictions,
            "timestamp": now_iso(),
        }

    # ---- 网络分析 ----

    def network_analysis(self, check_exposed: bool = True) -> dict[str, Any]:
        """网络连接分析."""
        conns: list[dict[str, Any]] = []
        status_counts: dict[str, int] = {}
        exposed_ports: list[dict[str, Any]] = []

        try:
            for conn in psutil.net_connections(kind="inet"):
                status = conn.status
                status_counts[status] = status_counts.get(status, 0) + 1

                entry: dict[str, Any] = {
                    "fd": conn.fd,
                    "family": str(conn.family),
                    "type": str(conn.type),
                    "local": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "",
                    "remote": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "",
                    "status": status,
                    "pid": conn.pid,
                }
                conns.append(entry)

                # 检查暴露端口
                if check_exposed and status == "LISTEN" and conn.laddr:
                    ip = conn.laddr.ip
                    port = conn.laddr.port
                    if ip in ("0.0.0.0", "::") and port in config.EXPOSED_RISKY_PORTS:
                        exposed_ports.append({
                            "port": port,
                            "bind": ip,
                            "pid": conn.pid,
                            "level": "严重" if port in (6379, 4444, 27017) else "高",
                        })
        except psutil.AccessDenied:
            return {"error": "权限不足，需 root 查看完整连接", "partial": True}

        # 异常外连检测
        suspicious: list[dict[str, Any]] = []
        remote_ips: dict[str, int] = {}
        for c in conns:
            if c["status"] == "ESTABLISHED" and c["remote"]:
                ip = c["remote"].split(":")[0]
                remote_ips[ip] = remote_ips.get(ip, 0) + 1
        for ip, count in remote_ips.items():
            if count > 20:
                suspicious.append({"ip": ip, "connections": count, "reason": "连接数异常偏高"})

        net = psutil.net_io_counters()
        return {
            "total_connections": len(conns),
            "status_distribution": status_counts,
            "exposed_ports": exposed_ports,
            "suspicious_remotes": suspicious,
            "traffic": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv,
            },
            "timestamp": now_iso(),
        }

    # ---- 告警回调 ----

    async def on_alert(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """响应监控告警 — 补充健康上下文."""
        etype = str(event.get("type", ""))
        if etype not in ("CPU 占用过高", "高危新进程", "敏感文件变更"):
            return None
        # 采集当前快照作为上下文
        snap = self.take_snapshot()
        return {
            "action": "health_context",
            "health_snapshot": snap.to_dict(),
            "recommendation": self._recommend_from_alert(event, snap),
        }

    def _recommend_from_alert(self, event: dict[str, Any], snap: HealthSnapshot) -> str:
        etype = str(event.get("type", ""))
        if "CPU" in etype:
            if snap.load_ratio > 2:
                return f"系统负载偏高（{snap.load_ratio:.1f}x），建议排查高 CPU 进程或扩容"
            return "建议查看 Top 进程列表确认 CPU 消耗来源"
        if "进程" in etype:
            return "建议核对进程详情后再决定是否拦截"
        return "建议人工复核"

    # ---- 工具处理器 ----

    async def _tool_full_check(self) -> str:
        snap = self.take_snapshot()
        result: dict[str, Any] = {
            "snapshot": snap.to_dict(),
            "status": "告警" if snap.alerts else "正常",
            "alert_count": len(snap.alerts),
        }
        # 附加趋势摘要
        if len(self._history) >= 3:
            for metric in ("cpu", "memory", "disk"):
                trend = self.analyze_trend(metric, last_n=min(20, len(self._history)))
                result[f"{metric}_trend"] = trend.get("trend", "unknown")
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_trend(self, metric: str = "all", last_n: int = 20) -> str:
        if metric == "all":
            result = {}
            for m in ("cpu", "memory", "disk", "load"):
                result[m] = self.analyze_trend(m, last_n)
            return json.dumps(result, ensure_ascii=False, indent=2)
        return json.dumps(self.analyze_trend(metric, last_n), ensure_ascii=False, indent=2)

    async def _tool_threshold_check(self) -> str:
        snap = self.take_snapshot()
        result = {
            "thresholds": self._thresholds,
            "current": {
                "cpu": snap.cpu_percent,
                "memory": snap.memory_percent,
                "disk": snap.disk_percent,
                "swap": snap.swap_percent,
                "load_ratio": round(snap.load_ratio, 2),
            },
            "alerts": snap.alerts,
            "all_ok": len(snap.alerts) == 0,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_disk_analysis(self) -> str:
        return json.dumps(self.disk_analysis(), ensure_ascii=False, indent=2)

    async def _tool_network_analysis(self, check_exposed: bool = True) -> str:
        return json.dumps(self.network_analysis(check_exposed), ensure_ascii=False, indent=2)

    async def _tool_get_history(self, limit: int = 60) -> str:
        history = list(self._history)[-limit:]
        return json.dumps(
            {
                "count": len(history),
                "snapshots": [s.to_dict() for s in history],
            },
            ensure_ascii=False,
            indent=2,
        )


# ---- 全局实例 ----
skill_instance = HealthCheckSkill()


# ---- 定时巡检入口（供 Cron 调用）----

def scheduled_check() -> dict[str, Any]:
    """定时健康巡检，返回结果（供 Cron 脚本调用）."""
    skill = HealthCheckSkill()
    snap = skill.take_snapshot()
    result = {
        "ts": snap.ts,
        "status": "告警" if snap.alerts else "正常",
        "cpu": snap.cpu_percent,
        "memory": snap.memory_percent,
        "disk": snap.disk_percent,
        "load_ratio": round(snap.load_ratio, 2),
        "alerts": snap.alerts,
    }
    # 写入文件供报告读取
    report_path = config.DATA_DIR / "health_latest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = scheduled_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
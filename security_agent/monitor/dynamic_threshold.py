"""动态阈值计算 — 基于历史数据的自适应阈值.

替代硬编码阈值（CPU 80%/Memory 90%/Disk 85%），
使用移动平均 + 标准差动态计算合理上限。

参考 Prometheus alerting 最佳实践：
  threshold = mean + (2.0 ~ 3.0) * stddev
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from pathlib import Path
from typing import Any

from security_agent import config

_HISTORY_PATH = config.DATA_DIR / "metrics_history.json"
_MAX_HISTORY = 360  # 保留最近 360 个采样点（每小时一个 = 15 天）


class DynamicThreshold:
    """自适应阈值引擎.

    原理:
      - 维护滚动窗口的历史指标采样
      - 阈值 = mean + k * stddev（k 默认 2.5）
      - 同时保留下限边界（不低于硬编码最小值）
    """

    def __init__(self):
        self._history: deque[dict[str, float]] = deque(maxlen=_MAX_HISTORY)
        self._k_factor: float = 2.5  # 标准差倍数
        self._floor = {  # 硬编码下限（永远不低于此值）
            "cpu": 70.0,
            "memory": 80.0,
            "disk": 75.0,
        }
        self._load()

    # ---- 采样 ----

    def record(self, cpu: float, memory: float, disk: float) -> None:
        """记录一个采样点."""
        self._history.append({
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "ts": time.time(),
        })
        if len(self._history) % 10 == 0:  # 每 10 个采样点持久化一次
            self._save()

    def _load(self) -> None:
        try:
            if _HISTORY_PATH.exists():
                data = json.loads(_HISTORY_PATH.read_text())
                for item in data[-_MAX_HISTORY:]:
                    self._history.append(item)
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_PATH.write_text(
            json.dumps(list(self._history), ensure_ascii=False)
        )

    # ---- 阈值计算 ----

    def compute(self) -> dict[str, Any]:
        """计算当前动态阈值.

        Returns:
            {
                "cpu_threshold": float,
                "memory_threshold": float,
                "disk_threshold": float,
                "history_size": int,
                "k_factor": float,
                "mean": {cpu, memory, disk},
                "stddev": {cpu, memory, disk},
            }
        """
        if len(self._history) < 5:
            # 样本不足时使用硬编码默认值
            return {
                "cpu_threshold": 80.0,
                "memory_threshold": 90.0,
                "disk_threshold": 85.0,
                "history_size": len(self._history),
                "k_factor": self._k_factor,
                "mean": {},
                "stddev": {},
                "mode": "static",
            }

        metrics = ("cpu", "memory", "disk")
        means = {}
        stds = {}
        thresholds = {}

        for m in metrics:
            values = [h[m] for h in self._history if m in h]
            if not values:
                continue
            n = len(values)
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            std = math.sqrt(variance)

            means[m] = round(mean, 2)
            stds[m] = round(std, 2)

            # 动态阈值 = mean + k * stddev，但不低于 floor
            raw = mean + self._k_factor * std
            thresholds[f"{m}_threshold"] = round(max(raw, self._floor.get(m, 60)), 1)

        return {
            **thresholds,
            "history_size": len(self._history),
            "k_factor": self._k_factor,
            "mean": means,
            "stddev": stds,
            "mode": "dynamic" if len(self._history) >= 5 else "static",
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def check(self, metric: str, value: float) -> dict[str, Any]:
        """检查指标是否超过动态阈值."""
        t = self.compute()
        key = f"{metric}_threshold"
        threshold = t.get(key, 80.0)
        alert = value > threshold
        return {
            "metric": metric,
            "value": value,
            "threshold": threshold,
            "alert": alert,
            "headroom_pct": round((1 - value / threshold) * 100, 1) if threshold > 0 else 0,
        }

    @property
    def history_size(self) -> int:
        return len(self._history)


# ---- 全局单例 ----

_instance: DynamicThreshold | None = None


def get_dynamic_threshold() -> DynamicThreshold:
    global _instance
    if _instance is None:
        _instance = DynamicThreshold()
    return _instance


# ---- 便捷：采样当前系统指标 ----

def record_current_metrics() -> dict[str, Any] | None:
    """采样当前系统指标并记录到动态阈值引擎."""
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent

        dt = get_dynamic_threshold()
        dt.record(cpu, mem, disk)

        return dt.compute()
    except Exception:
        return None

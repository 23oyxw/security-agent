"""FrequencyThrottle — 按告警等级分级节流，防止单源刷屏.

设计原则（不打扰）:
    每个 (source, type) 组合独立节流。
    P0 致命告警可以频繁（最小 15 秒间隔），
    P3 低等告警每 15 分钟最多 1 条。
    节流期间的事件不丢失 — 积压计数在下次发射时一并报告。

与现有 alert_aggregator 的分工:
    - alert_aggregator: 多事件合并（"磁盘告警 ×5"）
    - FrequencyThrottle: 单源频率控制（"同源告警 30 秒内不重复推送"）
    两者组合形成完整降噪链。

用法:
    from security_agent.notify.throttle import FrequencyThrottle

    throttle = FrequencyThrottle()
    should, reason = throttle.should_emit("monitor:cpu_alert", grade="P1")
    if should:
        send_notification(...)
    else:
        # 被节流，积压计数在下次发射时一并报告
"""

from __future__ import annotations

import time
from typing import Any


# 每个告警等级的最少推送间隔（秒）
GRADE_INTERVALS: dict[str, float] = {
    "P0": 15,    # 致命告警可以频繁
    "P1": 60,    # 严重告警每分钟最多 1 条
    "P2": 300,   # 中等告警每 5 分钟最多 1 条
    "P3": 900,   # 低等告警每 15 分钟最多 1 条
}

# 相同 key 的最大积压数（超过后丢弃最旧的）
MAX_PENDING_PER_KEY = 50

# 「暂时忽略」的默认时长（秒）
SNOOZE_DURATION = 3600  # 1 小时


class FrequencyThrottle:
    """每个告警类型独立节流。

    生命周期:
        throttle = FrequencyThrottle()
        # 每次有告警事件时调用:
        ok, meta = throttle.should_emit(key, grade)
        # 用户主动点了「暂时忽略」:
        throttle.snooze(key, duration_sec=3600)
    """

    def __init__(self):
        self._last_emit: dict[str, float] = {}       # key → 上次发射时间戳
        self._pending: dict[str, int] = {}            # key → 积压计数
        self._snoozed: dict[str, float] = {}          # key → snooze 到期时间戳

    # ---- 核心 ----

    def should_emit(self, key: str, *, grade: str = "P2") -> tuple[bool, str, int]:
        """判断同源告警现在是否应该推送。

        Args:
            key: 告警源+类型的唯一标识（如 "monitor:cpu_alert"）
            grade: 告警等级 P0/P1/P2/P3

        Returns:
            (should_emit, reason, pending_count)
            - should_emit: True = 可以推送
            - reason: 决策原因（人类可读）
            - pending_count: 当前积压数（发射时 >0 表示有被合并的告警）
        """
        now = time.time()

        # 1. Snooze 检查（用户主动点了「暂时忽略」）
        if key in self._snoozed:
            if now < self._snoozed[key]:
                self._pending[key] = self._pending.get(key, 0) + 1
                remaining = int(self._snoozed[key] - now)
                return False, f"snoozed ({remaining}s remaining)", self._pending.get(key, 0)
            else:
                del self._snoozed[key]

        # 2. 频率检查
        min_interval = GRADE_INTERVALS.get(grade, 300)
        last = self._last_emit.get(key, 0)
        elapsed = now - last

        if elapsed < min_interval:
            # 在窗口内，节流
            self._pending[key] = min(self._pending.get(key, 0) + 1, MAX_PENDING_PER_KEY)
            remaining = int(min_interval - elapsed)
            return False, f"throttled ({remaining}s until next allowed)", self._pending[key]

        # 3. 可以发射
        pending = self._pending.pop(key, 0)
        self._last_emit[key] = now

        if pending > 0:
            return True, f"emit (merged {pending} suppressed events)", pending

        return True, "emit", 0

    # ---- Snooze ----

    def snooze(self, key: str, duration_sec: int = SNOOZE_DURATION) -> None:
        """用户主动暂时忽略某类告警。

        Args:
            key: 告警唯一标识
            duration_sec: 忽略时长（默认 3600 秒 = 1 小时）
        """
        self._snoozed[key] = time.time() + duration_sec

    def unsnooze(self, key: str) -> bool:
        """取消暂时忽略。

        Returns:
            True 如果确实有 snooze 被取消
        """
        if key in self._snoozed:
            del self._snoozed[key]
            return True
        return False

    def is_snoozed(self, key: str) -> bool:
        """检查某类告警是否处于忽略状态."""
        if key not in self._snoozed:
            return False
        if time.time() >= self._snoozed[key]:
            del self._snoozed[key]
            return False
        return True

    # ---- 查询 ----

    def pending_count(self, key: str) -> int:
        return self._pending.get(key, 0)

    def total_pending(self) -> int:
        return sum(self._pending.values())

    def status(self) -> dict[str, Any]:
        return {
            "active_throttles": len(self._last_emit),
            "pending_total": self.total_pending(),
            "snoozed_count": len(self._snoozed),
            "snoozed_keys": list(self._snoozed.keys()),
        }

    def reset(self) -> None:
        """重置所有状态（用于测试）."""
        self._last_emit.clear()
        self._pending.clear()
        self._snoozed.clear()


# 全局单例（与现有 alert_aggregator 同级）
_throttle: FrequencyThrottle | None = None


def get_throttle() -> FrequencyThrottle:
    global _throttle
    if _throttle is None:
        _throttle = FrequencyThrottle()
    return _throttle

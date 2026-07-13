"""FloatingNotificationController — 智能浮屏控制.

设计原则（不打扰 + 可解释）:
    不是每条告警都需要弹窗。系统根据「有多少未读 + 最严重的是什么级别」
    自动决定浮屏形式：silent → badge → toast → banner → modal。

浮屏矩阵:

                    频率低              频率高
             ┌─────────────────┬─────────────────┐
    严重     │ 桌面通知 + 横幅   │ 模态框提醒       │
   (P0/P1)  │ "磁盘即将爆满"    │ "5台主机同时异常" │
             ├─────────────────┼─────────────────┤
    中等     │ 侧栏角标 +1      │ Toast 摘要       │
   (P2/P3)  │ 用户自己决定看    │ "过去1h: 3条告警" │
             ├─────────────────┼─────────────────┤
    信息     │ 只写日志          │ 聚合为统计数字    │
   (info)   │ 用户不需要感知    │ "今日: 42条正常"  │
             └─────────────────┴─────────────────┘

用法:
    from security_agent.notify.floating import FloatingController, FloatingAction

    fc = FloatingController()
    action = fc.decide(
        event={"level": "高", "type": "CPU告警", "message": "CPU 95%"},
        unread_count=4,
        recent_alert_count=3,
    )
    # action.level = "banner" → 顶部横幅提醒
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 严重度 → P 级映射
_SEVERITY_TO_GRADE: dict[str, str] = {
    "严重": "P0",
    "critical": "P0",
    "高": "P1",
    "high": "P1",
    "中": "P2",
    "medium": "P2",
    "低": "P3",
    "low": "P3",
    "信息": "info",
    "info": "info",
}


@dataclass(frozen=True)
class FloatingAction:
    """一次浮屏决策."""
    level: str         # silent | badge | toast | banner | modal
    title: str         # 通知标题
    body: str          # 通知正文（截断到 240 字符）
    urgency: str       # critical | normal | low
    duration_sec: int  # 显示时长（0 = 需手动关闭）

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "title": self.title,
            "body": self.body[:240],
            "urgency": self.urgency,
            "duration_sec": self.duration_sec,
        }


class FloatingController:
    """浮屏通知决策引擎.

    输入: 当前事件 + 上下文（未读数、最近告警数）
    输出: FloatingAction — 前端根据 level 执行对应的 UI 行为
    """

    # 浮屏行为矩阵: (最高严重度, 最近告警数) → (浮屏级别, 时长)
    MATRIX = {
        # (grade, recent_count_range) → (level, duration_sec, urgency)
        # P0 + 少量 → 横幅 10 秒
        ("P0", "low"):   ("banner", 10, "critical"),
        # P0 + 中量 → 横幅持续
        ("P0", "mid"):   ("banner", 0, "critical"),
        # P0 + 大量 → 模态框
        ("P0", "high"):  ("modal", 0, "critical"),

        # P1 + 少量 → 静默角标
        ("P1", "low"):   ("badge", 0, "normal"),
        # P1 + 中量 → Toast 5 秒
        ("P1", "mid"):   ("toast", 5, "normal"),
        # P1 + 大量 → 横幅 8 秒
        ("P1", "high"):  ("banner", 8, "critical"),

        # P2 + 任意 → Toast 3 秒
        ("P2", "low"):   ("toast", 3, "low"),
        ("P2", "mid"):   ("toast", 3, "low"),
        ("P2", "high"):  ("toast", 5, "normal"),

        # P3 + 任意 → 静默（只记日志）
        ("P3", "low"):   ("silent", 0, "low"),
        ("P3", "mid"):   ("silent", 0, "low"),
        ("P3", "high"):  ("badge", 0, "low"),

        # info → 永远静默
        ("info", "low"):  ("silent", 0, "low"),
        ("info", "mid"):  ("silent", 0, "low"),
        ("info", "high"): ("silent", 0, "low"),
    }

    def __init__(self):
        self._history: list[tuple[float, str]] = []  # (timestamp, grade)

    def decide(
        self,
        event: dict[str, Any],
        *,
        unread_count: int = 0,
        recent_alert_count: int | None = None,
        window_minutes: int = 5,
    ) -> FloatingAction:
        """决定这个告警事件应该如何呈现给用户.

        Args:
            event: 告警事件 {"level": "高", "type": "CPU告警", "message": "..."}
            unread_count: 当前未读告警数
            recent_alert_count: 最近窗口内的告警数（None = 自动计算）
            window_minutes: 窗口大小（分钟）

        Returns:
            FloatingAction — 前端据此渲染对应的 UI 组件
        """
        import time

        now = time.time()
        level = str(event.get("level", "低"))
        grade = _SEVERITY_TO_GRADE.get(level, "P2")
        message = str(event.get("message", ""))[:240]
        etype = str(event.get("type", "事件"))

        # 1. 清理过期历史
        cutoff = now - window_minutes * 60
        self._history = [(ts, g) for ts, g in self._history if ts > cutoff]

        # 2. 记录本次
        self._history.append((now, grade))

        # 3. 计算最近告警密度
        if recent_alert_count is None:
            recent_alert_count = len(self._history)

        bucket = self._frequency_bucket(recent_alert_count)

        # 4. 查矩阵
        matrix_key = (grade, bucket)
        float_level, duration, urgency = self.MATRIX.get(
            matrix_key, ("toast", 3, "normal")
        )

        # 5. 构造通知
        if float_level == "silent":
            title = ""
            body = ""
        elif float_level == "badge":
            title = f"[{level}] {etype}"
            body = f"{message}（共 {unread_count} 条未读）"
        elif float_level == "modal":
            title = f"⚠️ [{level}] {etype}"
            body = f"{message}\n\n当前未读告警: {unread_count} 条\n过去 {window_minutes} 分钟: {recent_alert_count} 条\n请尽快处理。"
        elif float_level == "banner":
            title = f"[{level}] {etype}"
            body = message
        else:  # toast
            title = f"[{level}] {etype}"
            body = message

        return FloatingAction(
            level=float_level,
            title=title,
            body=body,
            urgency=urgency,
            duration_sec=duration,
        )

    @staticmethod
    def _frequency_bucket(count: int) -> str:
        """将告警数量映射到低频/中频/高频桶."""
        if count <= 2:
            return "low"
        elif count <= 8:
            return "mid"
        else:
            return "high"

    def status(self) -> dict[str, Any]:
        return {
            "recent_count": len(self._history),
            "recent_grades": [g for _, g in self._history[-10:]],
        }


# 全局单例
_floating: FloatingController | None = None


def get_floating() -> FloatingController:
    global _floating
    if _floating is None:
        _floating = FloatingController()
    return _floating

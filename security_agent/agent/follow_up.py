"""多轮对话中的短句确认 / 续办意图."""

from __future__ import annotations

import re
from typing import Any

_AFFIRMATIVE = frozenset(
    {
        "需要",
        "好的",
        "好",
        "可以",
        "行",
        "执行",
        "处理",
        "关闭",
        "同意",
        "确认",
        "按方案",
        "方案一",
        "方案1",
        "帮我处理",
        "帮我关闭",
        "去做",
        "继续",
    }
)


def _last_assistant_text(history: list[dict[str, Any]]) -> str:
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            c = msg.get("content")
            if isinstance(c, str) and c.strip():
                return c
    return ""


def _extract_pid(text: str) -> int | None:
    m = re.search(r"PID\s*[：:]?\s*(\d{2,6})", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\|\s*\*\*(\d{4,6})\*\*", text)
    if m:
        return int(m.group(1))
    m = re.search(r"pid[:\s]+(\d{2,6})", text, re.I)
    if m:
        return int(m.group(1))
    return None


def is_short_affirmative(user_message: str) -> bool:
    t = (user_message or "").strip()
    if not t or len(t) > 24:
        return False
    if t in _AFFIRMATIVE:
        return True
    return any(t == w or t.startswith(w) for w in _AFFIRMATIVE)


def resolve_follow_up(user_message: str, history: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """短句续办：返回 {intent, skill_flow?, enriched_message, hint } 或 None."""
    if not is_short_affirmative(user_message):
        return None
    prev = _last_assistant_text(history or [])
    if not prev:
        return None

    low = prev.lower()
    pid = _extract_pid(prev)

    # 上轮建议关闭 VNC / vino-server
    if "vino-server" in low or "5900" in prev or "vnc" in low:
        if any(k in prev for k in ("killall", "关闭", "禁用", "方案一")):
            return {
                "intent": "secure_exec_flow",
                "skill_flow": "secure_exec",
                "enriched_message": "安全执行 killall vino-server",
                "hint": "用户确认处置 VNC 暴露，执行关闭 vino-server",
            }
        if pid:
            return {
                "intent": "block",
                "skill_flow": "block_process",
                "enriched_message": f"拦截进程 {pid}",
                "hint": f"用户确认处置，终止 PID {pid}",
            }

    if pid and any(k in prev for k in ("拦截", "终止", "kill", "处置")):
        return {
            "intent": "block",
            "skill_flow": "block_process",
            "enriched_message": f"拦截进程 {pid}",
            "hint": f"用户确认拦截 PID {pid}",
        }

    if any(k in prev for k in ("扫描报告", "生成报告", "HTML 报告")):
        return {
            "intent": "scan_report",
            "skill_flow": "scan_report",
            "enriched_message": "生成扫描报告",
            "hint": "用户确认生成报告",
        }

    return {
        "intent": "parallel_info",
        "enriched_message": "快速复查系统安全状态（进程与端口）",
        "hint": "用户简短确认，执行轻量复查而非全量 ReAct",
    }

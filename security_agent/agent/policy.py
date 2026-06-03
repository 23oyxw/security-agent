"""Risk classification and recommended actions."""

from __future__ import annotations

from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    CRITICAL = "严重"
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"
    INFO = "信息"


LEVEL_ORDER = {
    RiskLevel.CRITICAL: 4,
    RiskLevel.HIGH: 3,
    RiskLevel.MEDIUM: 2,
    RiskLevel.LOW: 1,
    RiskLevel.INFO: 0,
}


def classify_risk(risk: dict[str, Any]) -> RiskLevel:
    raw = risk.get("level", "中")
    for level in RiskLevel:
        if level.value == raw or level.name.lower() == str(raw).lower():
            return level
    return RiskLevel.MEDIUM


def should_auto_warn(risks: list[dict[str, Any]]) -> bool:
    return any(LEVEL_ORDER[classify_risk(r)] >= LEVEL_ORDER[RiskLevel.HIGH] for r in risks)


def should_auto_block(_risks: list[dict[str, Any]]) -> bool:
    """策略层禁止自动拦截，仅允许用户/UI/LLM 在用户确认后调用 block 工具."""
    return False


def recommend_action(risk: dict[str, Any]) -> str:
    rtype = risk.get("type", "")
    if rtype == "高危进程" and "pid" in risk:
        return f"建议审查或拦截 PID {risk['pid']}"
    if rtype == "权限异常":
        return "建议收紧文件权限并核查最近变更"
    return "建议人工复核"


def summarize_risks(risks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {level.value: 0 for level in RiskLevel}
    for risk in risks:
        counts[classify_risk(risk).value] += 1
    return counts

"""告警升级策略引擎 — 自动/半自动/人工三级分流.

流程:
  告警事件 → 分级 → 路由到 Skill on_alert → 汇总 → 执行/通知
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from security_agent.audit import log as audit
from security_agent.timeutil import now_iso


class EscalationAction(str, Enum):
    AUTO_FIX = "auto_fix"              # 自动修复（低风险自愈）
    NOTIFY_AND_SUGGEST = "notify"      # 通知 + 建议（需人工确认执行）
    NOTIFY_ONLY = "notify_only"        # 仅通知（记录 + 桌面弹窗）
    IGNORE = "ignore"                  # 忽略（信息级）


class EscalationLevel(str, Enum):
    CRITICAL = "critical"   # 立即响应
    HIGH = "high"           # 尽快响应
    MEDIUM = "medium"       # 正常排期
    LOW = "low"             # 记录即可


# ---- 升级规则 ----
# A2赛题核心：告警分级 + 自动修复策略
ESCALATION_RULES: dict[str, dict[str, Any]] = {
    # 监控事件类型 → 升级级别 + 动作
    "CPU 占用过高": {
        "level": EscalationLevel.HIGH,
        "action": EscalationAction.NOTIFY_AND_SUGGEST,
        "auto_threshold": 95,  # CPU > 95% 时升级为 auto_fix（自愈清理）
        "auto_fix_level": EscalationLevel.MEDIUM,  # 低于阈值时可自动修复
    },
    "磁盘空间不足": {
        "level": EscalationLevel.HIGH,
        "action": EscalationAction.NOTIFY_AND_SUGGEST,
        "auto_threshold": 90,  # 磁盘 > 90% 告警，< 95% 可自动清理
        "auto_fix_level": EscalationLevel.MEDIUM,
    },
    "内存占用过高": {
        "level": EscalationLevel.HIGH,
        "action": EscalationAction.NOTIFY_AND_SUGGEST,
        "auto_threshold": 90,
        "auto_fix_level": EscalationLevel.MEDIUM,
    },
    "僵尸进程": {
        "level": EscalationLevel.MEDIUM,
        "action": EscalationAction.AUTO_FIX,  # 低风险，可直接清理
    },
    "日志文件过大": {
        "level": EscalationLevel.MEDIUM,
        "action": EscalationAction.AUTO_FIX,  # 可自动轮转
    },
    "临时文件堆积": {
        "level": EscalationLevel.LOW,
        "action": EscalationAction.AUTO_FIX,  # 低风险清理
    },
    "高危新进程": {
        "level": EscalationLevel.CRITICAL,
        "action": EscalationAction.NOTIFY_AND_SUGGEST,
    },
    "敏感文件变更": {
        "level": EscalationLevel.HIGH,
        "action": EscalationAction.NOTIFY_AND_SUGGEST,
    },
    "登录失败暴破": {
        "level": EscalationLevel.CRITICAL,
        "action": EscalationAction.NOTIFY_AND_SUGGEST,
    },
    "新增监听端口": {
        "level": EscalationLevel.HIGH,
        "action": EscalationAction.NOTIFY_ONLY,
    },
    "Cron 变更": {
        "level": EscalationLevel.MEDIUM,
        "action": EscalationAction.NOTIFY_ONLY,
    },
    "监控错误": {
        "level": EscalationLevel.LOW,
        "action": EscalationAction.NOTIFY_ONLY,
    },
    "新进程": {
        "level": EscalationLevel.LOW,
        "action": EscalationAction.IGNORE,
    },
    "心跳": {
        "level": EscalationLevel.LOW,
        "action": EscalationAction.IGNORE,
    },
    "监控启动": {
        "level": EscalationLevel.LOW,
        "action": EscalationAction.IGNORE,
    },
    "监控停止": {
        "level": EscalationLevel.LOW,
        "action": EscalationAction.NOTIFY_ONLY,
    },
}

# 等级覆盖（严重/高 事件强制升级）
LEVEL_OVERRIDES: dict[str, EscalationAction] = {
    "严重": EscalationAction.NOTIFY_AND_SUGGEST,
    "高": EscalationAction.NOTIFY_AND_SUGGEST,
}


@dataclass
class EscalationResult:
    """升级策略执行结果."""

    ts: str
    event_type: str
    event_level: str
    escalation_level: EscalationLevel
    action: EscalationAction
    skill_responses: list[dict[str, Any]] = field(default_factory=list)
    auto_fix_result: dict[str, Any] = field(default_factory=dict)
    notification_sent: bool = False
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "event_type": self.event_type,
            "event_level": self.event_level,
            "escalation_level": self.escalation_level.value,
            "action": self.action.value,
            "skill_responses": self.skill_responses,
            "auto_fix_result": self.auto_fix_result,
            "notification_sent": self.notification_sent,
            "summary": self.summary,
        }


class EscalationEngine:
    """告警升级策略引擎.

    工作流:
    1. 接收监控事件
    2. 按规则确定升级级别和动作
    3. 路由到相关 Skill 的 on_alert
    4. 根据 Skill 返回决定是否自动修复
    5. 发送通知（桌面/文件）
    """

    def __init__(self) -> None:
        self._history: list[EscalationResult] = []

    async def process_event(self, event: dict[str, Any]) -> EscalationResult:
        """处理一个监控事件."""
        etype = str(event.get("type", ""))
        level = str(event.get("level", ""))
        ts = now_iso()

        # 1. 确定升级级别和动作
        rule = ESCALATION_RULES.get(etype, {})
        escalation_level = rule.get("level", EscalationLevel.MEDIUM)
        action = rule.get("action", EscalationAction.NOTIFY_ONLY)

        # 等级覆盖
        if level in LEVEL_OVERRIDES:
            action = LEVEL_OVERRIDES[level]

        result = EscalationResult(
            ts=ts,
            event_type=etype,
            event_level=level,
            escalation_level=escalation_level,
            action=action,
        )

        # 2. 忽略低优先级事件
        if action == EscalationAction.IGNORE:
            result.summary = "忽略"
            return result

        # 3. 路由到 Skill（延迟导入避免循环）
        try:
            from security_agent.skills.registry import route_alert_to_skills
            skill_responses = await route_alert_to_skills(event)
            result.skill_responses = skill_responses
        except Exception as exc:  # noqa: BLE001
            result.skill_responses = [{"error": str(exc)}]

        # 4. 自动修复（仅限 AUTO_FIX 动作）
        if action == EscalationAction.AUTO_FIX:
            result.auto_fix_result = await self._try_auto_fix(event, result)

        # 5. 生成摘要
        result.summary = self._build_summary(result)

        # 6. 审计
        audit.append_audit(
            "escalation",
            {
                "event_type": etype,
                "level": level,
                "escalation": escalation_level.value,
                "action": action.value,
                "skill_count": len(result.skill_responses),
            },
            level="warning" if escalation_level in (EscalationLevel.CRITICAL, EscalationLevel.HIGH) else "info",
        )

        self._history.append(result)
        return result

    async def _try_auto_fix(
        self, event: dict[str, Any], result: EscalationResult
    ) -> dict[str, Any]:
        """尝试自动修复（仅低风险操作）.
        
        A2赛题核心场景：自动识别风险 → 安全校验 → 受限执行 → 日志溯源
        """
        etype = str(event.get("type", ""))
        level = str(event.get("level", ""))
        
        # 只有低/中级别且明确允许自动修复的事件才执行
        if level in ("严重", "高", "CRITICAL", "HIGH"):
            return {"ok": False, "reason": "高危事件需人工确认，不自动修复", "level": level}

        try:
            from security_agent.skills.incident_responder.skill import (
                IncidentResponderSkill, SELF_HEAL_SCRIPTS
            )
            from security_agent.terminal.executor import run_terminal_sync
            from security_agent.rules.engine import RuleVerdict

            responder = IncidentResponderSkill()
            
            # 根据事件类型选择诊断策略
            diagnosis_map = {
                "CPU 占用过高": "high_cpu",
                "磁盘空间不足": "disk_full", 
                "内存占用过高": "high_memory",
                "僵尸进程": "zombie_processes",
            }
            
            diagnosis_key = diagnosis_map.get(etype)
            if not diagnosis_key:
                return {"ok": False, "reason": f"事件类型 {etype} 暂无自动修复策略"}

            # 1. 诊断阶段（OS环境感知）
            diagnosis = responder.auto_diagnose(diagnosis_key)
            if not diagnosis.auto_fix_available:
                return {
                    "ok": False, 
                    "reason": "诊断结果表明不适合自动修复",
                    "diagnosis": diagnosis.to_dict()
                }

            # 2. 安全校验阶段 - 校验命令是否在白名单
            fix_cmd = diagnosis.auto_fix_command
            allowed_scripts = {
                sid: script for sid, script in SELF_HEAL_SCRIPTS.items()
                if script.get("auto_ok") and script.get("command") == fix_cmd
            }
            
            if not allowed_scripts:
                return {
                    "ok": False, 
                    "reason": "修复命令不在预定义低风险白名单中",
                    "command": fix_cmd
                }

            # 3. 执行前记录审计（推理链路溯源）
            script_id = list(allowed_scripts.keys())[0]
            audit.append_audit(
                "auto_fix_start",
                {
                    "event_type": etype,
                    "event_level": level,
                    "script_id": script_id,
                    "command": fix_cmd,
                    "diagnosis": diagnosis.to_dict(),
                },
                level="info"
            )

            # 4. 最小权限执行 - 使用run_terminal_sync走完整安全门控
            exec_result = run_terminal_sync(
                fix_cmd,
                timeout_sec=30.0,
                user_confirmed=True,  # 自动修复视为系统级确认
            )

            # 5. 执行后审计
            success = exec_result.ok and exec_result.exit_code == 0
            audit.append_audit(
                "auto_fix_complete" if success else "auto_fix_failed",
                {
                    "event_type": etype,
                    "script_id": script_id,
                    "success": success,
                    "exit_code": exec_result.exit_code,
                    "stdout": exec_result.stdout[:500],
                    "stderr": exec_result.stderr[:500],
                },
                level="info" if success else "warning"
            )

            return {
                "ok": success,
                "name": script_id,
                "command": fix_cmd,
                "exit_code": exec_result.exit_code,
                "stdout": exec_result.stdout,
                "stderr": exec_result.stderr,
                "diagnosis": diagnosis.to_dict(),
            }

        except Exception as exc:
            audit.append_audit("auto_fix_error", {"error": str(exc)}, level="error")
            return {"ok": False, "error": str(exc), "reason": "自动修复过程异常"}

    def _build_summary(self, result: EscalationResult) -> str:
        """构建人类可读的摘要."""
        parts = [
            f"[{result.escalation_level.value.upper()}] {result.event_type} ({result.event_level})",
        ]
        if result.skill_responses:
            for resp in result.skill_responses:
                if resp.get("recommendation"):
                    parts.append(f"  → {resp['recommendation']}")
                if resp.get("action") == "incident_response":
                    summary = resp.get("plan_summary", {})
                    parts.append(f"  → 故障: {summary.get('root_cause', '未知')}")
        if result.auto_fix_result.get("ok"):
            parts.append(f"  → 已自动修复: {result.auto_fix_result.get('name', '')}")
        elif result.action == EscalationAction.AUTO_FIX:
            parts.append("  → 自动修复失败，需人工介入")
        return "\n".join(parts)

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._history[-limit:]]


# ---- 全局实例 ----
_engine: EscalationEngine | None = None


def get_escalation_engine() -> EscalationEngine:
    global _engine
    if _engine is None:
        _engine = EscalationEngine()
    return _engine
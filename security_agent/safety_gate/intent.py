"""动态意图审计 — 交叉校验Agent指令与用户原始意图的一致性（赛题核心得分点）.

功能：
  1. 提取用户原始意图的关键词/操作类型
  2. 检查Agent实际执行的指令类型与用户意图是否偏离
  3. 偏离检测：读变成写、低风险变高风险、类型转换等
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntentCategory(Enum):
    """用户意图分类."""
    OBSERVE = "observe"          # 观测/监控类
    SCAN = "scan"                # 安全扫描类
    REPORT = "report"            # 报告生成类
    MODIFY = "modify"            # 修改配置/执行变更
    BLOCK = "block"              # 拦截/阻断
    INSTALL = "install"          # 安装部署
    REMOVE = "remove"            # 卸载删除
    BACKUP = "backup"            # 备份
    RESTORE = "restore"          # 恢复/回滚
    ANALYSIS = "analysis"        # 分析/诊断
    DEMO = "demo"                # 演练/测试
    UNKNOWN = "unknown"          # 未分类


@dataclass
class IntentAuditResult:
    """意图审计结果."""
    matched: bool                          # 是否匹配
    user_intent: str = ""                  # 提取的用户意图描述
    intent_category: IntentCategory = IntentCategory.UNKNOWN
    agent_action: str = ""                 # Agent实际执行的指令
    action_category: IntentCategory = IntentCategory.UNKNOWN
    deviation: float = 0.0                 # 偏离度 (0-1), 越高越危险
    deviation_reason: str = ""             # 偏离原因
    risk_upgrade: bool = False             # 是否从低风险升级到高风险操作
    intent_mismatch: bool = False          # 意图不匹配
    audit_id: str = ""                     # 审计记录ID
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "user_intent": self.user_intent,
            "intent_category": self.intent_category.value,
            "agent_action": self.agent_action,
            "action_category": self.action_category.value if self.action_category else "unknown",
            "deviation": self.deviation,
            "deviation_reason": self.deviation_reason,
            "risk_upgrade": self.risk_upgrade,
            "intent_mismatch": self.intent_mismatch,
            "audit_id": self.audit_id,
            "metadata": self.metadata,
        }


# 各类别关键词映射
_INTENT_KEYWORDS: dict[IntentCategory, list[str]] = {
    IntentCategory.OBSERVE: [
        "查看", "观察", "监控", "检查", "显示", "show", "list", "ps",
        "status", "health", "进程", "cpu", "内存", "磁盘", "网络",
        "连接", "端口", "log", "日志", "audit", "审计",
    ],
    IntentCategory.SCAN: [
        "扫描", "scan", "体检", "检查", "风险", "漏洞", "安全",
        "威胁", "vulnerability", "security",
    ],
    IntentCategory.REPORT: [
        "报告", "report", "报表", "summary", "总结", "摘要",
        "导出", "export", "html",
    ],
    IntentCategory.MODIFY: [
        "修改", "变更", "设置", "配置", "更新", "开启", "关闭",
        "启用", "禁用", "启动", "停止", "restart", "reload",
        "chmod", "chown", "sed", "mv", "cp", "重命名",
    ],
    IntentCategory.BLOCK: [
        "拦截", "终止", "kill", "block", "删除进程", "停止进程",
        "拦截进程", "pkill", "stop process",
    ],
    IntentCategory.INSTALL: [
        "安装", "部署", "install", "setup", "apt install", "pip install",
        "npm install", "docker pull", "docker run",
    ],
    IntentCategory.REMOVE: [
        "删除", "卸载", "remove", "uninstall", "rm", "purge",
        "autoremove", "docker rm", "docker rmi",
    ],
    IntentCategory.BACKUP: [
        "备份", "backup", "export", "dump", "save",
    ],
    IntentCategory.RESTORE: [
        "恢复", "回滚", "restore", "rollback", "revert", "reset",
    ],
    IntentCategory.ANALYSIS: [
        "分析", "诊断", "排查", "定位", "问题", "故障",
        "troubleshoot", "debug", "analyze",
    ],
    IntentCategory.DEMO: [
        "演练", "demo", "测试", "场景", "演示", "模拟",
    ],
}


# 越权行为模式 — Agent执行的操作与用户意图不一致的类型
_DEVIATION_PATTERNS: list[tuple[str, str, float]] = [
    # (模式描述, 正则匹配, 偏离度)
    ("观察变删除", r"(?i)(查看|检查|观察|show|list|ps).*(rm|删除|uninstall|purge)", 0.8),
    ("扫描变修改", r"(?i)(扫描|scan|检查).*(chmod|chown|配置|修改|变更)", 0.7),
    ("报告变执行", r"(?i)(报告|report|导出|export).*(执行|run|install|apt|pip)", 0.8),
    ("审计变破坏", r"(?i)(审计|audit|log|日志).*(rm|删除|格式化|mkfs|dd)", 1.0),
    ("只读变写入", r"(?i)(ps|ss|df|free|uptime|cat|head|tail|grep|ls).*(rm|chmod|chown|>|tee|sed)", 0.9),
    ("检查变入侵", r"(?i)(检查|查看|health|status).*(shell|eval|exec|bash|sh\s+-c)", 1.0),
]


class IntentAuditor:
    """动态意图审计器 — 交叉校验用户指令与Agent实际行为."""

    def extract_intent(self, user_message: str) -> tuple[str, IntentCategory]:
        """从用户消息中提取意图."""
        text = user_message.strip()
        if not text:
            return "空消息", IntentCategory.UNKNOWN

        # 按关键词权重匹配
        best_category = IntentCategory.UNKNOWN
        best_score = 0

        for category, keywords in _INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text.lower())
            if score > best_score:
                best_score = score
                best_category = category

        # 提取简洁的描述
        desc = text[:80] if len(text) > 80 else text

        return desc, best_category

    def classify_action(self, action: str) -> IntentCategory:
        """对Agent实际操作的指令进行分类."""
        for category, keywords in _INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw in action.lower():
                    return category
        return IntentCategory.UNKNOWN

    def detect_deviation(
        self,
        user_intent: str,
        user_category: IntentCategory,
        agent_action: str,
    ) -> tuple[float, str, bool]:
        """检测意图偏离.

        Returns:
            (偏离度, 原因, 是否风险升级)
        """
        # 1. 检查越权模式
        for desc, pattern, severity in _DEVIATION_PATTERNS:
            combined = f"{user_intent} {agent_action}"
            if re.search(pattern, combined, re.IGNORECASE):
                return (severity, f"越权模式: {desc}", severity >= 0.8)

        # 2. 如果无法分类用户意图，保守返回
        if user_category == IntentCategory.UNKNOWN:
            return (0.0, "用户意图未分类，放行", False)

        # 3. 基于类型比较的偏离检测
        action_category = self.classify_action(agent_action)

        # 安全操作升级检测
        safe_to_dangerous = {
            IntentCategory.OBSERVE: [IntentCategory.MODIFY, IntentCategory.BLOCK,
                                     IntentCategory.REMOVE, IntentCategory.INSTALL],
            IntentCategory.SCAN: [IntentCategory.MODIFY, IntentCategory.REMOVE],
            IntentCategory.REPORT: [IntentCategory.MODIFY, IntentCategory.REMOVE],
            IntentCategory.ANALYSIS: [IntentCategory.MODIFY, IntentCategory.REMOVE],
        }

        upgrade_targets = safe_to_dangerous.get(user_category, [])
        if action_category in upgrade_targets:
            return (
                0.6,
                f"操作升级: 用户意图为{user_category.value}，Agent执行{action_category.value}操作",
                True,
            )

        # 类型完全匹配 → 无偏离
        if action_category == user_category:
            return (0.0, "意图一致", False)

        return (0.0, "可接受的意图差异", False)

    def audit(
        self,
        user_message: str,
        agent_action: str,
        *,
        audit_id: str = "",
    ) -> IntentAuditResult:
        """执行完整的意图审计.

        Args:
            user_message: 用户原始消息
            agent_action: Agent实际执行的指令
            audit_id: 审计记录ID

        Returns:
            IntentAuditResult
        """
        intent_desc, intent_cat = self.extract_intent(user_message)
        action_cat = self.classify_action(agent_action)
        deviation, reason, risk_upgrade = self.detect_deviation(
            intent_desc, intent_cat, agent_action,
        )

        # 偏离度 > 0.5 判定为不匹配
        mismatched = deviation > 0.5

        return IntentAuditResult(
            matched=not mismatched,
            user_intent=intent_desc,
            intent_category=intent_cat,
            agent_action=agent_action,
            action_category=action_cat,
            deviation=deviation,
            deviation_reason=reason,
            risk_upgrade=risk_upgrade,
            intent_mismatch=mismatched,
            audit_id=audit_id,
        )
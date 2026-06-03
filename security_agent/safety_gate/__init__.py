"""SafetyGate — 独立于LLM的同步安全闸门（赛题核心得分点）.

架构定位：
  用户指令 → SafetyGate → [通过] → LLM/Agent → 操作执行
              ↑                    ↓
              └── 拦截/确认/回滚 ←──┘

四级风险判定：
  READONLY  - 只读操作，自动放行
  REVERSIBLE - 可逆操作，需确认
  IRREVERSIBLE - 不可逆操作，需用户明确授权
  CRITICAL  - 关键操作，需人工审批 + 自动备份

三层防护：
  1. 静态规则引擎（规则库拦截高危指令）
  2. 动态意图审计（交叉校验Agent指令与用户原始意图）
  3. 受限执行环境（沙箱执行 + 自动备份 + 一键回滚）
"""

from __future__ import annotations

from security_agent.safety_gate.gate import SafetyGate
from security_agent.safety_gate.risk import RiskAssessor, RiskLevel, RiskAssessment
from security_agent.safety_gate.intent import IntentAuditor, IntentAuditResult
from security_agent.safety_gate.snapshot import SnapshotManager, SnapshotRecord
from security_agent.safety_gate.injection_defense import (
    InjectionDefense,
    InjectionResult,
    get_injection_defense,
)
from security_agent.safety_gate.three_layer_defense import (
    ThreeLayerDefenseEngine,
    ThreeLayerDefenseResult,
    OverallVerdict,
)
from security_agent.safety_gate.mac_checker import KylinMACChecker, MacCheckResult, get_mac_checker

__all__ = [
    "SafetyGate",
    "RiskAssessor",
    "RiskLevel",
    "RiskAssessment",
    "IntentAuditor",
    "IntentAuditResult",
    "SnapshotManager",
    "SnapshotRecord",
    "InjectionDefense",
    "InjectionResult",
    "get_injection_defense",
    "ThreeLayerDefenseEngine",
    "ThreeLayerDefenseResult",
    "OverallVerdict",
    "KylinMACChecker",
    "MacCheckResult",
    "get_mac_checker",
]
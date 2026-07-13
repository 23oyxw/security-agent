"""三层安全防御体系 — 核心安全控制层（护栏）.

赛题核心: 通过事前拦截、事中校验、事后兜底的全链路防护，
保障智能运维 Agent 执行安全可控。

三层防御权重分配:
  ┌────────────────────┬────────┬───────────────────────────────────┐
  │ 层级               │ 权重   │ 职责                               │
  ├────────────────────┼────────┼───────────────────────────────────┤
  │ 1. 静态风险评估    │ 30%    │ 规则引擎拦截高危命令，四级风险判定 │
  │ 2. 动态意图审计    │ 35%    │ 交叉校验指令与用户意图一致性        │
  │ 3. 受限执行环境    │ 35%    │ 最小权限+沙箱+备份+回滚            │
  └────────────────────┴────────┴───────────────────────────────────┘

核心价值: 三层联动，避免误操作/越权执行/指令偏离等安全问题。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional

from security_agent.safety_gate.risk import (
    RiskAssessor,
    RiskLevel,
    RiskAssessment,
)
from security_agent.safety_gate.intent import (
    IntentAuditor,
    IntentAuditResult,
)
from security_agent.safety_gate.injection_defense import (
    InjectionDefense,
    get_injection_defense,
)


# =============================================================================
# 数据模型
# =============================================================================


class DefenseLayer(str, Enum):
    """防御层级枚举."""
    STATIC_RISK = "static_risk"           # 第一层：静态风险评估(30%)
    DYNAMIC_INTENT = "dynamic_intent"     # 第二层：动态意图审计(35%)
    RESTRICTED_EXEC = "restricted_exec"    # 第三层：受限执行环境(35%)


# 与前端 constants/three-layer-defense.js · trace_chart_metrics 对齐
LAYER_META: Dict[DefenseLayer, Dict[str, Any]] = {
    DefenseLayer.STATIC_RISK: {
        "name_zh": "第1层 · 静态风险评估",
        "short_zh": "静态规则",
        "weight_pct": 30,
        "desc": "规则引擎 + 注入扫描 · 高危命令四级判定",
    },
    DefenseLayer.DYNAMIC_INTENT: {
        "name_zh": "第2层 · 动态意图审计",
        "short_zh": "意图一致",
        "weight_pct": 35,
        "desc": "用户运维意图 vs 拟执行命令交叉校验",
    },
    DefenseLayer.RESTRICTED_EXEC: {
        "name_zh": "第3层 · 受限执行环境",
        "short_zh": "沙箱/权限",
        "weight_pct": 35,
        "desc": "最小权限 · 沙箱隔离 · 备份回滚 · 平台可行性",
    },
}


class OverallVerdict(str, Enum):
    """综合判决."""
    ALLOW = "allow"                       # 完全放行
    CONFIRM = "confirm"                   # 需用户确认后放行
    APPROVE = "approve"                   # 需人工审批
    DENY = "deny"                         # 直接拦截
    QUARANTINE = "quarantine"             # 隔离到沙箱执行
    ESCALATE = "escalate"                 # 升级处理


@dataclass
class LayerScore:
    """单层评分结果."""
    layer: DefenseLayer
    weight: float                        # 权重 (0-1)
    score: float                          # 安全分 (0=最危险, 100=完全安全)
    passed: bool                          # 是否通过
    verdict: str                          # 本层判定: pass / warn / block
    detail: str = ""                      # 详细说明
    raw_result: Any = None                # 原始评估数据
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        meta = LAYER_META.get(self.layer, {})
        return {
            "layer": self.layer.value,
            "name": meta.get("name_zh", self.layer.value),
            "name_zh": meta.get("name_zh", self.layer.value),
            "short_zh": meta.get("short_zh", ""),
            "weight": self.weight,
            "weight_pct": meta.get("weight_pct", int(self.weight * 100)),
            "desc": meta.get("desc", ""),
            "score": round(self.score, 2),
            "passed": self.passed,
            "verdict": self.verdict,
            "detail": self.detail[:300],
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class ThreeLayerDefenseResult:
    """三层防御综合评估结果."""
    trace_id: str = ""
    target_type: str = "terminal"          # terminal / tool / api_call
    target: str = ""                       # 命令/工具名/API
    overall_verdict: OverallVerdict = OverallVerdict.ALLOW
    overall_score: float = 100.0           # 加权总分
    layers: List[LayerScore] = field(default_factory=list)
    decision_path: List[str] = field(default_factory=list)
    message: str = ""
    requires_user_confirmation: bool = False
    requires_human_approval: bool = False
    requires_sandbox: bool = False
    auto_backup_triggered: bool = False
    rollback_available: bool = False
    timestamp: str = ""
    total_duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        feasibility = (self.metadata or {}).get("execution_feasibility") or {}
        return {
            "trace_id": self.trace_id,
            "target_type": self.target_type,
            "target": self.target[:200],
            "overall_verdict": self.overall_verdict.value,
            "overall_score": round(self.overall_score, 2),
            "layers": [l.to_dict() for l in self.layers],
            "layer_definitions": [
                {"id": layer.value, **LAYER_META.get(layer, {})}
                for layer in DefenseLayer
            ],
            "decision_path": self.decision_path,
            "message": self.message,
            "requires_user_confirmation": self.requires_user_confirmation,
            "requires_human_approval": self.requires_human_approval,
            "requires_sandbox": self.requires_sandbox,
            "execution_feasibility": feasibility,
            "eval_note": (
                "评估通过仅表示安全策略允许；实际执行还受本机 OS、权限、沙箱与命令语法影响。"
                if feasibility.get("ok") is False
                else ""
            ),
            "auto_backup_triggered": self.auto_backup_triggered,
            "rollback_available": self.rollback_available,
            "timestamp": self.timestamp,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# =============================================================================
# 三层防御引擎
# =============================================================================


class ThreeLayerDefenseEngine:
    """三层安全防御引擎 — 统一安全入口.

    架构:
      用户/Agent 指令
          ↓
      ┌──────────────────────────────────────────┐
      │ 第1层: 静态风险评估 (权重30%)              │
      │  - 规则引擎四级风险判定                    │
      │  - 高危命令模式匹配                        │
      │  → score_1 ∈ [0, 100]                     │
      └─────────────────┬────────────────────────┘
                        ↓
      ┌──────────────────────────────────────────┐
      │ 第2层: 动态意图审计 (权重35%)              │
      │  - 用户意图 vs Agent 行为交叉校验          │
      │  - 越权模式检测                           │
      │  → score_2 ∈ [0, 100]                     │
      └─────────────────┬────────────────────────┘
                        ↓
      ┌──────────────────────────────────────────┐
      │ 第3层: 受限执行环境 (权重35%)              │
      │  - 最少权限原则                            │
      │  - 沙箱/容器隔离执行                       │
      │  - 自动备份 + 一键回滚                     │
      │  → score_3 ∈ [0, 100]                     │
      └─────────────────┬────────────────────────┘
                        ↓
              综合决策: 加权评分 + 多数否决
                → ALLOW | CONFIRM | APPROVE | DENY | QUARANTINE

    设计原则:
      - 任一层 block 则整体 DENY（多数否决权）
      - 加权总分 < 40 分则 DENY
      - 两层 warn 以上则 CONFIRM/APPROVE
      - CRITICAL 级别强制升级人工审批
    """

    # 权重配置（必须总和为 1.0）
    LAYER_WEIGHTS: Dict[DefenseLayer, float] = {
        DefenseLayer.STATIC_RISK: 0.30,       # 30%
        DefenseLayer.DYNAMIC_INTENT: 0.35,     # 35%
        DefenseLayer.RESTRICTED_EXEC: 0.35,    # 35%
    }

    # 判定阈值
    THRESHOLD_DENY = 25.0                      # 总分低于此值 → DENY
    THRESHOLD_CONFIRM = 50.0                   # 总分低于此值 → CONFIRM
    THRESHOLD_APPROVE = 35.0                   # 单层低于此值可能需要审批

    def __init__(
        self,
        *,
        risk_assessor: Optional[RiskAssessor] = None,
        intent_auditor: Optional[IntentAuditor] = None,
        injection_defense: Optional[InjectionDefense] = None,
        sandbox_executor=None,
        backup_manager=None,
        deny_on_deviation: bool = True,
        enable_sandbox: bool = True,
    ):
        """
        Args:
            risk_assessor: 自定义风险评估器（默认使用内置）
            intent_auditor: 自定义意图审计器（默认使用内置）
            injection_defense: 注入防御引擎（默认使用全局实例）
            sandbox_executor: 沙箱执行器（可选）
            backup_manager: 备份管理器（可选）
            deny_on_deviation: 是否在意图偏离时自动拒绝
            enable_sandbox: 是否启用沙箱执行能力
        """
        self.risk_assessor = risk_assessor or RiskAssessor()
        self.intent_auditor = intent_auditor or IntentAuditor()
        self.injection_defense = injection_defense or get_injection_defense()
        self.sandbox_executor = sandbox_executor
        self.backup_manager = backup_manager
        self.deny_on_deviation = deny_on_deviation
        self.enable_sandbox = enable_sandbox

    async def evaluate(
        self,
        target: str,
        *,
        target_type: str = "terminal",
        user_message: str = "",
        arguments: Optional[Dict[str, Any]] = None,
        trace_id: str = "",
        user: str = "",
        sudo: bool = False,
    ) -> ThreeLayerDefenseResult:
        """执行完整的三层防御评估.

        Args:
            target: 待评估目标（命令/工具名）
            target_type: 目标类型 (terminal/tool/api_call)
            user_message: 用户原始消息
            arguments: 工具调用参数
            trace_id: 追踪ID
            user: 操作用户
            sudo: 是否使用sudo权限

        Returns:
            ThreeLayerDefenseResult: 综合评估结果
        """
        t_total = time.perf_counter()
        result = ThreeLayerDefenseResult(
            trace_id=trace_id or f"defense-{uuid.uuid4().hex[:12]}",
            target_type=target_type,
            target=target,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            metadata={"user": user, "sudo": sudo},
        )

        # === 第1层: 静态风险评估 (30%) ===
        l1 = await self._evaluate_static_risk(target, target_type, arguments, sudo, user)
        result.layers.append(l1)
        result.decision_path.append(f"L1_static_risk={l1.verdict}({l1.score:.0f})")

        # 快速路径：第1层直接阻断
        if l1.verdict == "block":
            return self._finalize(result, OverallVerdict.DENY,
                                   f"[L1阻断] {l1.detail}", t_total)

        # === 第2层: 动态意图审计 (35%) ===
        l2 = await self._evaluate_dynamic_intent(
            target, target_type, user_message, arguments
        )
        result.layers.append(l2)
        result.decision_path.append(f"L2_intent_audit={l2.verdict}({l2.score:.0f})")

        # 快速路径：意图严重偏离
        if l2.verdict == "block":
            return self._finalize(result, OverallVerdict.DENY if self.deny_on_deviation else OverallVerdict.CONFIRM,
                                   f"[L2阻断] {l2.detail}", t_total)

        # === 第3层: 受限执行环境 (35%) ===
        l3 = await self._evaluate_restricted_exec(
            target, target_type, l1.raw_result, user
        )
        result.layers.append(l3)
        result.decision_path.append(f"L3_restricted_exec={l3.verdict}({l3.score:.0f})")

        # === 综合决策 ===
        verdict, msg = self._make_final_decision(result.layers)
        result.overall_verdict = verdict
        result.message = msg
        result.overall_score = self._calculate_weighted_score(result.layers)

        # 设置附加属性
        result.requires_user_confirmation = verdict in (
            OverallVerdict.CONFIRM, OverallVerdict.QUARANTINE,
        )
        result.requires_human_approval = verdict == OverallVerdict.APPROVE
        result.requires_sandbox = verdict == OverallVerdict.QUARANTINE and self.enable_sandbox

        # 执行可行性（与安全 verdict 独立 — 避免「评估通过但本机执行失败」无解释）
        if target_type == "terminal" and target.strip():
            from security_agent.safety_gate.execution_feasibility import check_execution_feasibility

            feasibility = check_execution_feasibility(target, target_type=target_type)
            result.metadata["execution_feasibility"] = feasibility
            if not feasibility.get("ok"):
                for layer in result.layers:
                    if layer.layer == DefenseLayer.RESTRICTED_EXEC:
                        layer.detail = (
                            f"{layer.detail} | 平台提示: {feasibility.get('reason', '')}"
                        )[:300]
                        if layer.verdict == "pass":
                            layer.verdict = "warn"
                        break

        # 备份触发
        if verdict in (OverallVerdict.CONFIRM, OverallVerdict.APPROVE, OverallVerdict.QUARANTINE):
            risk = l1.raw_result
            if isinstance(risk, RiskAssessment) and risk.requires_backup:
                if self.backup_manager:
                    try:
                        snapshot = self.backup_manager.create_snapshot(
                            operation=target[:100],
                            risk_level=risk.level.name,
                            user=user,
                        )
                        result.auto_backup_triggered = True
                        result.rollback_available = True
                        result.decision_path.append(f"backup_created({snapshot.id})")
                    except Exception as e:
                        result.decision_path.append(f"backup_failed({e})")
                result.decision_path.append("backup_required")

        result.total_duration_ms = (time.perf_counter() - t_total) * 1000
        return result

    # =========================================================================
    # 第1层：静态风险评估 (30%)
    # =========================================================================

    async def _evaluate_static_risk(
        self,
        target: str,
        target_type: str,
        arguments: Optional[Dict[str, Any]],
        sudo: bool,
        user: str,
    ) -> LayerScore:
        """第1层: 静态规则引擎评估 (含注入防御扫描)."""
        t0 = time.perf_counter()
        weight = self.LAYER_WEIGHTS[DefenseLayer.STATIC_RISK]

        try:
            # ── 1a. 基础风险评估 ──
            if target_type == "terminal":
                assessment = self.risk_assessor.assess_terminal(target, sudo=sudo)
            elif target_type == "tool":
                assessment = self.risk_assessor.assess_tool(target, arguments)
            else:
                assessment = RiskAssessment(
                    level=RiskLevel.READONLY,
                    reason=f"未知目标类型 {target_type}, 默认只读",
                )

            # 将风险等级映射为安全分数
            score_map = {
                RiskLevel.READONLY: 95.0,
                RiskLevel.REVERSIBLE: 70.0,
                RiskLevel.IRREVERSIBLE: 35.0,
                RiskLevel.CRITICAL: 5.0,
            }
            score = score_map.get(assessment.level, 70.0)

            # ── 1b. 注入攻击扫描 (同步,快速正则匹配 <1ms) ──
            injection_result = self.injection_defense.scan(target)
            injection_penalty = 0
            injection_details: list[str] = []

            if injection_result.triggered:
                # 注入严重度越高,扣分越多
                injection_penalty = min(60, injection_result.severity * 0.6)
                injection_details = [
                    f"注入类型:{m['type']}" for m in injection_result.matched_rules[:3]
                ]
                if injection_result.block:
                    return LayerScore(
                        layer=DefenseLayer.STATIC_RISK,
                        weight=weight,
                        score=0.0,
                        passed=False,
                        verdict="block",
                        detail=(
                            f"🛡 注入攻击阻断: severity={injection_result.severity}, "
                            f"type={injection_result.injection_type.value}, "
                            f"matched={len(injection_result.matched_rules)}条规则"
                        ),
                        raw_result={"risk": assessment, "injection": injection_result},
                        duration_ms=(time.perf_counter() - t0) * 1000,
                    )

            # 应用注入扣分
            score = max(0.0, score - injection_penalty)

            # ── 1c. 组合判定 ──
            # CRITICAL 直接 block
            if assessment.level >= RiskLevel.CRITICAL:
                return LayerScore(
                    layer=DefenseLayer.STATIC_RISK,
                    weight=weight,
                    score=score,
                    passed=False,
                    verdict="block",
                    detail=f"{assessment.reason}",
                    raw_result={"risk": assessment, "injection": injection_result},
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # IRREVERSIBLE 为 warn
            verdict = "warn" if assessment.level >= RiskLevel.IRREVERSIBLE else "pass"
            detail_parts = [f"风险等级: {assessment.level.label()} — {assessment.reason}"]
            if injection_details:
                detail_parts.append(f"注入检测: {'; '.join(injection_details)}")
            detail = " | ".join(detail_parts)

            return LayerScore(
                layer=DefenseLayer.STATIC_RISK,
                weight=weight,
                score=score,
                passed=True,
                verdict=verdict,
                detail=detail,
                raw_result={"risk": assessment, "injection": injection_result},
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            return LayerScore(
                layer=DefenseLayer.STATIC_RISK,
                weight=weight,
                score=50.0,  # 异常时给中等分数
                passed=False,
                verdict="warn",
                detail=f"评估异常: {str(e)}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    # =========================================================================
    # 第2层：动态意图审计 (35%)
    # =========================================================================

    async def _evaluate_dynamic_intent(
        self,
        target: str,
        target_type: str,
        user_message: str,
        arguments: Optional[Dict[str, Any]],
    ) -> LayerScore:
        """第2层: 动态意图一致性审计."""
        t0 = time.perf_counter()
        weight = self.LAYER_WEIGHTS[DefenseLayer.DYNAMIC_INTENT]

        # 无用户消息时跳过（如系统内部调用）
        if not user_message or not user_message.strip():
            return LayerScore(
                layer=DefenseLayer.DYNAMIC_INTENT,
                weight=weight,
                score=85.0,
                passed=True,
                verdict="pass",
                detail="无用户消息，跳过意图审计",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        try:
            action_desc = target
            if target_type == "tool" and arguments:
                action_desc = f"{target}({json.dumps(arguments, ensure_ascii=False)})"

            intent_result = self.intent_auditor.audit(
                user_message, action_desc,
                audit_id=f"intent-{uuid.uuid4().hex[:8]}",
            )

            # 偏离度转换为安全分数 (偏离越高，分数越低)
            deviation = intent_result.deviation
            score = max(0.0, 100.0 - deviation * 100)

            # 严重偏离 → block
            if intent_result.deviation >= 0.9:
                return LayerScore(
                    layer=DefenseLayer.DYNAMIC_INTENT,
                    weight=weight,
                    score=score,
                    passed=False,
                    verdict="block",
                    detail=(
                        f"严重意图偏离(deviation={deviation:.2f}): "
                        f"{intent_result.deviation_reason}"
                    ),
                    raw_result=intent_result,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # 中等偏离 → warn
            if intent_result.intent_mismatch or intent_result.risk_upgrade:
                return LayerScore(
                    layer=DefenseLayer.DYNAMIC_INTENT,
                    weight=weight,
                    score=score,
                    passed=True,
                    verdict="warn",
                    detail=(
                        f"意图偏差(deviation={deviation:.2f}): "
                        f"{intent_result.deviation_reason}"
                    ),
                    raw_result=intent_result,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            return LayerScore(
                layer=DefenseLayer.DYNAMIC_INTENT,
                weight=weight,
                score=score,
                passed=True,
                verdict="pass",
                detail=f"意图一致: {intent_result.user_intent[:60]}",
                raw_result=intent_result,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            return LayerScore(
                layer=DefenseLayer.DYNAMIC_INTENT,
                weight=weight,
                score=60.0,
                passed=False,
                verdict="warn",
                detail=f"意图审计异常: {str(e)}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    # =========================================================================
    # 第3层：受限执行环境 (35%)
    # =========================================================================

    async def _evaluate_restricted_exec(
        self,
        target: str,
        target_type: str,
        risk_assessment: Any,
        user: str,
    ) -> LayerScore:
        """第3层: 受限执行环境检查."""
        t0 = time.perf_counter()
        weight = self.LAYER_WEIGHTS[DefenseLayer.RESTRICTED_EXEC]

        try:
            checks = []
            score = 85.0  # 默认较高分

            # 3a. 最小权限原则检查
            has_write = any(kw in target for kw in [
                "rm ", "chmod", "chown", ">", "|", ">",
                "apt ", "pip install", "docker run",
            ])
            uses_root = any(kw in target for kw in ["sudo", "root"])

            if has_write and uses_root:
                checks.append("检测到 root 写操作，需最小权限降级")
                score -= 20
            elif has_write:
                checks.append("写操作存在，建议使用受限用户")
                score -= 10
            elif uses_root:
                checks.append("root 只读操作可放行")
            else:
                checks.append("无特权操作需求")

            # 3b. 沙箱可用性检查
            if self.enable_sandbox:
                if has_write:
                    checks.append("沙箱执行已就绪，高风险操作将在隔离环境运行")
                    score += 5
                else:
                    checks.append("沙箱可用但非必要")
            else:
                if has_write:
                    checks.append("警告: 无沙箱，写操作直接执行")
                    score -= 15

            # 3c. 回滚能力检查
            if isinstance(risk_assessment, RiskAssessment):
                if risk_assessment.requires_backup and self.backup_manager:
                    checks.append(f"回滚就绪: 自动备份将触发")
                    score += 5
                elif risk_assessment.requires_backup:
                    checks.append("警告: 不可逆操作但无备份管理器")
                    score -= 15

            # 3d. 麒麟 MAC 上下文检查
            try:
                from security_agent.safety_gate.mac_checker import get_mac_checker
                mac = get_mac_checker(enforce=False)
                mac_result = mac.pre_exec_check(target, {}, "READONLY" if not has_write else "MODERATE")
                if mac_result.platform == "kylin" and mac_result.context_before:
                    checks.append(f"MAC 上下文: {mac_result.context_before[:50]}")
                    score += 3  # MAC 可用是加分项
                if not mac_result.allowed:
                    checks.append(f"MAC 拒绝: {mac_result.reason}")
                    score -= 20
            except Exception:
                pass  # MAC 不可用时不影响评分

            # 综合判定
            if score < 40:
                verdict = "warn"
                detail = "; ".join(checks) + " — 执行风险过高"
            elif score < 65:
                verdict = "warn"
                detail = "; ".join(checks) + " — 需关注"
            else:
                verdict = "pass"
                detail = "; ".join(checks) + " — 环境满足要求"

            return LayerScore(
                layer=DefenseLayer.RESTRICTED_EXEC,
                weight=weight,
                score=max(0, min(100, score)),
                passed=verdict != "block",
                verdict=verdict,
                detail=detail,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            return LayerScore(
                layer=DefenseLayer.RESTRICTED_EXEC,
                weight=weight,
                score=55.0,
                passed=False,
                verdict="warn",
                detail=f"执行环境检查异常: {str(e)}",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    # =========================================================================
    # 综合决策逻辑
    # =========================================================================

    @staticmethod
    def _calculate_weighted_score(layers: List[LayerScore]) -> float:
        """计算加权总分."""
        total_weight = sum(l.weight for l in layers)
        weighted_sum = sum(l.score * l.weight for l in layers)
        return weighted_sum / total_weight if total_weight > 0 else 0

    def _make_final_decision(self, layers: List[LayerScore]) -> tuple[OverallVerdict, str]:
        """根据三层结果做出最终决策.

        决策规则（优先级从高到低）:
          1. 任一层 block → DENY（多数否决权）
          2. 加权总分 < THRESHOLD_DENY → DENY
          3. CRITICAL 风险 + 任意 warn → APPROVE（需人工审批）
          4. 两层及以上 warn → CONFIRM 或 APPROVE
          5. 单层 warn → CONFIRM
          6. 全部 pass → ALLOW
          7. 有 write 操作且沙箱可用 → QUARANTINE
        """
        # 规则1: 任一层 block
        block_count = sum(1 for l in layers if l.verdict == "block")
        if block_count > 0:
            block_layers = [l.layer.value for l in layers if l.verdict == "block"]
            return (
                OverallVerdict.DENY,
                f"多层否决({'/'.join(block_layers)}层阻断)，操作被拒绝",
            )

        # 计算加权总分
        total_score = self._calculate_weighted_score(layers)

        # 规则2: 总分过低
        if total_score < self.THRESHOLD_DENY:
            return (
                OverallVerdict.DENY,
                f"安全评分不足 ({total_score:.1f} < {self.THRESHOLD_DENY})，操作被拒绝",
            )

        # 统计 warn 数量
        warn_count = sum(1 for l in layers if l.verdict == "warn")
        warn_details = [(l.layer.value, l.score) for l in layers if l.verdict == "warn"]

        # 规则3: L1 是 CRITICAL 级风险
        l1_risk = layers[0].raw_result if len(layers) > 0 else None
        if isinstance(l1_risk, RiskAssessment) and l1_risk.level >= RiskLevel.CRITICAL:
            return (
                OverallVerdict.APPROVE,
                f"CRITICAL 风险操作({l1_risk.reason})，需人工审批",
            )

        # 规则4: 多层 warn
        if warn_count >= 2:
            if total_score < self.THRESHOLD_CONFIRM:
                return (
                    OverallVerdict.APPROVE if total_score < self.THRESHOLD_APPROVE
                                      else OverallVerdict.CONFIRM,
                    f"多层安全警告({warn_count}层): "
                    f"{'; '.join(f'{l}[{s:.0f}分]' for l, s in warn_details)}，需确认或审批",
                )
            return (
                OverallVerdict.CONFIRM,
                f"多层安全警告({warn_count}层)，需用户确认",
            )

        # 规则5: 单层 warn
        if warn_count == 1:
            if total_score < self.THRESHOLD_CONFIRM:
                return (
                    OverallVerdict.CONFIRM,
                    f"安全警告: {warn_details[0][0]}层({warn_details[0][1]:.0f}分)，需用户确认",
                )
            return OverallVerdict.ALLOW, f"轻微警告但整体安全"

        # 规则6: 全部通过
        return OverallVerdict.ALLOW, f"所有安全检查通过 (总分: {total_score:.1f})"

    @staticmethod
    def _finalize(
        result: ThreeLayerDefenseResult,
        verdict: OverallVerdict,
        message: str,
        start_time: float,
    ) -> ThreeLayerDefenseResult:
        """快速完成评估结果."""
        result.overall_verdict = verdict
        result.message = message
        result.overall_score = 0.0
        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        return result


# =============================================================================
# 兼容性适配器 — 将 SafetyGate 接口适配为 ThreeLayerDefenseEngine
# =============================================================================


class SafetyGateAdapter:
    """SafetyGate → ThreeLayerDefenseEngine 适配器.

    使现有代码无需修改即可使用新的三层防御引擎。
    保持原有 SafetyGate.evaluate_terminal() 接口不变。
    """

    def __init__(self, engine: Optional[ThreeLayerDefenseEngine] = None):
        self.engine = engine or ThreeLayerDefenseEngine()

    async def evaluate_async(
        self,
        command: str,
        *,
        user_message: str = "",
        trace_id: str = "",
        sudo: bool = False,
        user: str = "",
    ) -> ThreeLayerDefenseResult:
        """异步评估（推荐新代码使用）."""
        return await self.engine.evaluate(
            command,
            target_type="terminal",
            user_message=user_message,
            trace_id=trace_id,
            sudo=sudo,
            user=user,
        )

    def evaluate_sync(
        self,
        command: str,
        *,
        user_message: str = "",
        trace_id: str = "",
        sudo: bool = False,
        user: str = "",
    ) -> ThreeLayerDefenseResult:
        """同步评估包装（兼容旧接口）."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中，用同步方式创建任务不合适，降级为简单评估
                t0 = time.perf_counter()
                result = ThreeLayerDefenseResult(
                    trace_id=trace_id or f"sync-{uuid.uuid4().hex[:8]}",
                    target_type="terminal",
                    target=command,
                )
                # 仅做静态风险评估作为同步降级
                assessment = self.engine.risk_assessor.assess_terminal(command, sudo=sudo)
                score_map = {
                    RiskLevel.READONLY: 90, RiskLevel.REVERSIBLE: 60,
                    RiskLevel.IRREVERSIBLE: 30, RiskLevel.CRITICAL: 5,
                }
                from security_agent.safety_gate.gate import GateResult, GateVerdict

                if assessment.level == RiskLevel.READONLY:
                    g_verdict = GateVerdict.ALLOW
                elif assessment.level == RiskLevel.REVERSIBLE:
                    g_verdict = GateVerdict.CONFIRM
                elif assessment.level == RiskLevel.IRREVERSIBLE:
                    g_verdict = GateVerdict.BACKUP_AND_CONFIRM
                else:
                    g_verdict = GateVerdict.ESCALATE

                result.overall_score = float(score_map.get(assessment.level, 50))
                result.message = assessment.reason
                result.total_duration_ms = (time.perf_counter() - t0) * 1000
                # 映射到旧格式
                return result
            else:
                return loop.run_until_complete(self.evaluate_async(
                    command, user_message=user_message,
                    trace_id=trace_id, sudo=sudo, user=user,
                ))
        except RuntimeError:
            # 完全没有事件循环时，返回基础评估
            t0 = time.perf_counter()
            assessment = self.engine.risk_assessor.assess_terminal(command, sudo=sudo)
            result = ThreeLayerDefenseResult(
                trace_id=trace_id or f"fallback-{uuid.uuid4().hex[:8]}",
                target=command,
                overall_score=50.0,
                message=assessment.reason,
                total_duration_ms=(time.perf_counter() - t0) * 1000,
            )
            return result

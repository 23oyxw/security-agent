"""SafetyGate — 统一安全闸门，集成三级防护.

架构：
  用户/Agent指令 → RiskAssessor (四级判定) → IntentAuditor (意图交叉校验) 
  → 决策引擎 → [放行 | 需确认 | 需审批 | 拦截]

  在 IRREVERSIBLE 操作前自动触发 SnapshotManager 备份。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from security_agent.safety_gate.risk import RiskAssessor, RiskLevel, RiskAssessment
from security_agent.safety_gate.intent import IntentAuditor, IntentAuditResult
from security_agent.safety_gate.snapshot import SnapshotManager, SnapshotRecord
from security_agent.confirm import get_confirmation_manager, ConfirmationLevel as ConfirmLevel


class GateVerdict(str, Enum):
    """闸门最终判定."""
    ALLOW = "allow"                   # 自动放行
    CONFIRM = "confirm"               # 需要用户确认
    APPROVE = "approve"               # 需要人工审批
    DENY = "deny"                     # 直接拦截
    BACKUP_AND_CONFIRM = "backup_confirm"  # 备份 + 需确认
    ESCALATE = "escalate"             # 升级到人工审批流程


@dataclass
class GateResult:
    """闸门判定结果."""
    verdict: GateVerdict
    risk: RiskAssessment | None = None
    intent: IntentAuditResult | None = None
    snapshot: SnapshotRecord | None = None
    decision_path: list[str] = field(default_factory=list)
    trace_id: str = ""
    duration_ms: float = 0.0
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "message": self.message,
            "decision_path": self.decision_path,
            "trace_id": self.trace_id,
            "duration_ms": round(self.duration_ms, 2),
            "risk": self.risk.to_dict() if self.risk else None,
            "intent": self.intent.to_dict() if self.intent else None,
            "snapshot_id": self.snapshot.id if self.snapshot else None,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class SafetyGate:
    """统一安全闸门.

    三级防护集成：
      1. 静态规则引擎 (RiskAssessor)
      2. 动态意图审计 (IntentAuditor)
      3. 受限执行环境 & 自动备份 (SnapshotManager)

    用法:
        gate = SafetyGate()
        result = gate.evaluate_terminal(
            user_message="查看系统进程",
            command="ps aux",
            trace_id="trace-xxx",
        )
        if result.verdict == GateVerdict.ALLOW:
            # 执行命令
            pass
        elif result.verdict == GateVerdict.CONFIRM:
            # 展示确认对话框
            pass
    """

    def __init__(
        self,
        snapshot_base_dir: str | None = None,
        auto_backup: bool = True,
        deny_on_deviation: bool = True,
    ):
        self.risk_assessor = RiskAssessor()
        self.intent_auditor = IntentAuditor()
        self.snapshot_manager = SnapshotManager(base_dir=snapshot_base_dir)
        self.auto_backup = auto_backup
        self.deny_on_deviation = deny_on_deviation
        self._trace_id: str = ""

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def evaluate_terminal(
        self,
        command: str,
        *,
        user_message: str = "",
        trace_id: str = "",
        sudo: bool = False,
        user: str = "",
    ) -> GateResult:
        """终端命令安全判定."""
        start = time.perf_counter()
        self._trace_id = trace_id or f"gate-{uuid.uuid4().hex[:12]}"
        decision_path: list[str] = []
        metadata: dict[str, Any] = {
            "command": command,
            "sudo": sudo,
            "user": user,
        }

        # ---- 第一步：四级风险判定 ----
        risk = self.risk_assessor.assess_terminal(command, sudo=sudo)
        decision_path.append(f"risk={risk.level.name}({risk.level.label()})")

        # ---- 第二步：意图审计（如有用户消息） ----
        intent_result: IntentAuditResult | None = None
        if user_message:
            intent_result = self.intent_auditor.audit(
                user_message, command, audit_id=self._trace_id,
            )
            if intent_result.intent_mismatch:
                decision_path.append(
                    f"intent_mismatch(deviation={intent_result.deviation:.2f})"
                )
                metadata["intent_deviation_reason"] = intent_result.deviation_reason
            else:
                decision_path.append("intent_pass")
        else:
            decision_path.append("intent_skip")

        # ---- 第三步：综合决策 ----
        # 1. 意图严重偏离（越权模式）→ 直接拦截
        if (
            intent_result
            and intent_result.deviation >= 0.9
            and self.deny_on_deviation
        ):
            duration = (time.perf_counter() - start) * 1000
            return GateResult(
                verdict=GateVerdict.DENY,
                risk=risk,
                intent=intent_result,
                decision_path=decision_path + ["DENY_by_intent_deviation"],
                trace_id=self._trace_id,
                duration_ms=duration,
                message=f"意图严重偏离: {intent_result.deviation_reason}",
                metadata=metadata,
            )

        # 2. CRITICAL → 升级到人工审批
        if risk.level == RiskLevel.CRITICAL:
            duration = (time.perf_counter() - start) * 1000
            return GateResult(
                verdict=GateVerdict.ESCALATE,
                risk=risk,
                intent=intent_result,
                decision_path=decision_path + ["ESCALATE_by_critical"],
                trace_id=self._trace_id,
                duration_ms=duration,
                message=f"CRITICAL风险: {risk.reason}，需人工审批",
                metadata=metadata,
            )

        # 3. IRREVERSIBLE → 备份 + 需用户明确授权
        if risk.level == RiskLevel.IRREVERSIBLE:
            snapshot = None
            if self.auto_backup and risk.requires_backup:
                # 尝试自动备份
                try:
                    snapshot = self.snapshot_manager.create_snapshot(
                        operation=command[:100],
                        risk_level=risk.level.name,
                        user=user,
                    )
                    decision_path.append(f"snapshot_created({snapshot.id})")
                except Exception as exc:
                    decision_path.append(f"snapshot_failed({exc})")

            # 检查意图是否有偏差
            if intent_result and intent_result.risk_upgrade:
                verdict = GateVerdict.ESCALATE
                msg = f"意图风险升级+不可逆操作: {risk.reason}"
                decision_path.append("ESCALATE_by_risk_upgrade")
            else:
                verdict = GateVerdict.BACKUP_AND_CONFIRM
                msg = f"不可逆操作，已备份，需用户明确授权: {risk.reason}"
                decision_path.append("BACKUP_AND_CONFIRM")

            duration = (time.perf_counter() - start) * 1000
            return GateResult(
                verdict=verdict,
                risk=risk,
                intent=intent_result,
                snapshot=snapshot,
                decision_path=decision_path,
                trace_id=self._trace_id,
                duration_ms=duration,
                message=msg,
                metadata=metadata,
            )

        # 4. REVERSIBLE → 需用户确认
        if risk.level == RiskLevel.REVERSIBLE:
            # 意图风险升级 → 升级到审批
            if intent_result and intent_result.risk_upgrade:
                duration = (time.perf_counter() - start) * 1000
                return GateResult(
                    verdict=GateVerdict.ESCALATE,
                    risk=risk,
                    intent=intent_result,
                    decision_path=decision_path + ["ESCALATE_by_risk_upgrade"],
                    trace_id=self._trace_id,
                    duration_ms=duration,
                    message=f"意图风险升级: {intent_result.deviation_reason}",
                    metadata=metadata,
                )

            duration = (time.perf_counter() - start) * 1000
            return GateResult(
                verdict=GateVerdict.CONFIRM,
                risk=risk,
                intent=intent_result,
                decision_path=decision_path + ["CONFIRM_by_reversible"],
                trace_id=self._trace_id,
                duration_ms=duration,
                message=f"可逆操作，需确认: {risk.reason}",
                metadata=metadata,
            )

        # 5. READONLY → 自动放行
        duration = (time.perf_counter() - start) * 1000
        return GateResult(
            verdict=GateVerdict.ALLOW,
            risk=risk,
            intent=intent_result,
            decision_path=decision_path + ["ALLOW_by_readonly"],
            trace_id=self._trace_id,
            duration_ms=duration,
            message="只读操作，自动放行",
            metadata=metadata,
        )

    def evaluate_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        user_message: str = "",
        trace_id: str = "",
        user: str = "",
    ) -> GateResult:
        """工具调用安全判定."""
        start = time.perf_counter()
        self._trace_id = trace_id or f"gate-{uuid.uuid4().hex[:12]}"
        decision_path: list[str] = []
        metadata: dict[str, Any] = {
            "tool": tool_name,
            "args": arguments or {},
            "user": user,
        }

        # ---- 第一步：四级风险判定 ----
        risk = self.risk_assessor.assess_tool(tool_name, arguments)
        decision_path.append(f"risk={risk.level.name}({risk.level.label()})")

        # ---- 第二步：意图审计 ----
        intent_result: IntentAuditResult | None = None
        if user_message:
            action_desc = f"{tool_name}({json.dumps(arguments or {}, ensure_ascii=False)})"
            intent_result = self.intent_auditor.audit(
                user_message, action_desc, audit_id=self._trace_id,
            )
            if intent_result.intent_mismatch:
                decision_path.append(
                    f"intent_mismatch(deviation={intent_result.deviation:.2f})"
                )
            else:
                decision_path.append("intent_pass")
        else:
            decision_path.append("intent_skip")

        # ---- 第三步：综合决策 ----
        # CRITICAL
        if risk.level == RiskLevel.CRITICAL:
            duration = (time.perf_counter() - start) * 1000
            return GateResult(
                verdict=GateVerdict.ESCALATE,
                risk=risk,
                intent=intent_result,
                decision_path=decision_path + ["ESCALATE_by_critical"],
                trace_id=self._trace_id,
                duration_ms=duration,
                message=f"高危工具调用: {risk.reason}，需人工审批",
                metadata=metadata,
            )

        # IRREVERSIBLE
        if risk.level == RiskLevel.IRREVERSIBLE:
            snapshot = None
            if self.auto_backup and risk.requires_backup:
                try:
                    snapshot = self.snapshot_manager.create_snapshot(
                        operation=f"tool:{tool_name}",
                        risk_level=risk.level.name,
                        user=user,
                    )
                    decision_path.append(f"snapshot_created({snapshot.id})")
                except Exception as exc:
                    decision_path.append(f"snapshot_failed({exc})")

            duration = (time.perf_counter() - start) * 1000
            return GateResult(
                verdict=GateVerdict.BACKUP_AND_CONFIRM,
                risk=risk,
                intent=intent_result,
                snapshot=snapshot,
                decision_path=decision_path + ["BACKUP_AND_CONFIRM"],
                trace_id=self._trace_id,
                duration_ms=duration,
                message=f"不可逆工具操作，已备份，需授权: {risk.reason}",
                metadata=metadata,
            )

        # REVERSIBLE
        if risk.level == RiskLevel.REVERSIBLE:
            duration = (time.perf_counter() - start) * 1000
            return GateResult(
                verdict=GateVerdict.CONFIRM,
                risk=risk,
                intent=intent_result,
                decision_path=decision_path + ["CONFIRM_by_reversible"],
                trace_id=self._trace_id,
                duration_ms=duration,
                message=f"可逆工具操作，需确认: {risk.reason}",
                metadata=metadata,
            )

        # READONLY
        duration = (time.perf_counter() - start) * 1000
        return GateResult(
            verdict=GateVerdict.ALLOW,
            risk=risk,
            intent=intent_result,
            decision_path=decision_path + ["ALLOW_by_readonly"],
            trace_id=self._trace_id,
            duration_ms=duration,
            message="只读工具，自动放行",
            metadata=metadata,
        )
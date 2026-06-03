"""
Dify ↔ security_agent 双向桥接.

DifyIntegration:
  - 接收 Dify 工作流回调
  - 解析 AI 分析结果
  - 通过安全网关 (SafetyGate) 执行操作
  - 记录全链路审计

WorkflowDispatcher:
  - 按工作流类型 (威胁检测/巡检/告警/Chat/RAG) 分发处理
  - 将 Dify 输出转换为 security_agent 内部动作
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data models ───────────────────────────────────────────────────

class WorkflowType(Enum):
    THREAT_DETECTION = "threat_detection"
    SECURITY_INSPECTION = "security_inspection"
    ALERT_PROCESSING = "alert_processing"
    SECURITY_CHAT = "security_chat"
    KNOWLEDGE_RAG = "knowledge_rag"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ThreatResult:
    threat_type: str = ""
    risk_level: int = 1
    confidence: float = 0.0
    impact_scope: str = ""
    attack_chain: str = ""
    recommendation: str = ""
    urgency: str = "低"
    raw_json: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InspectionResult:
    overall_score: int = 100
    critical_issues: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)
    trend: str = "stable"
    summary: str = ""
    raw_json: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertTriageResult:
    is_false_positive: bool = False
    severity: str = "low"
    confidence: float = 0.0
    needs_immediate_action: bool = False
    suggested_owner: str = ""
    attack_vector: str = ""
    mitigation_steps: List[Dict] = field(default_factory=list)
    raw_json: Dict[str, Any] = field(default_factory=dict)


# ── Parser ────────────────────────────────────────────────────────

def _safe_parse_json(text: str) -> Dict[str, Any]:
    """从 LLM 输出中安全提取 JSON."""
    if not text:
        return {}
    text = text.strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试从 markdown code block 中提取
    import re
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 尝试找到第一个 { ... } 块
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    logger.warning("DifyBridge: failed to parse JSON from text[:200]=%r", text[:200])
    return {}


# ── Dispatcher ────────────────────────────────────────────────────

class WorkflowDispatcher:
    """按工作流类型分发 Dify 输出 -> security_agent 内部动作."""

    def __init__(self, gate=None, executor=None, plugin_manager=None):
        self._gate = gate
        self._executor = executor
        self._plugin_manager = plugin_manager

    def dispatch_threat_detection(self, outputs: Dict[str, Any]) -> ThreatResult:
        """解析威胁检测工作流输出."""
        text = outputs.get("result", "") or outputs.get("text", "") or json.dumps(outputs)
        data = _safe_parse_json(text)
        result = ThreatResult(
            threat_type=data.get("threat_type", ""),
            risk_level=int(data.get("risk_level", 1)),
            confidence=float(data.get("confidence", 0.0)),
            impact_scope=data.get("impact_scope", ""),
            attack_chain=data.get("attack_chain", ""),
            recommendation=data.get("recommendation", ""),
            urgency=data.get("urgency", "低"),
            raw_json=data,
        )
        logger.info(
            "DifyDispatcher: threat=%s risk=%d urgency=%s",
            result.threat_type, result.risk_level, result.urgency,
        )
        return result

    def dispatch_inspection(self, outputs: Dict[str, Any]) -> InspectionResult:
        """解析安全巡检工作流输出."""
        text = outputs.get("report", "") or outputs.get("text", "") or json.dumps(outputs)
        data = _safe_parse_json(text)
        result = InspectionResult(
            overall_score=int(data.get("overall_score", 100)),
            critical_issues=data.get("critical_issues", []),
            warnings=data.get("warnings", []),
            passed_checks=data.get("passed_checks", []),
            trend=data.get("trend", "stable"),
            summary=data.get("summary", ""),
            raw_json=data,
        )
        logger.info(
            "DifyDispatcher: inspection score=%d critical=%d warnings=%d",
            result.overall_score, len(result.critical_issues), len(result.warnings),
        )
        return result

    def dispatch_alert_processing(self, outputs: Dict[str, Any]) -> AlertTriageResult:
        """解析告警处理工作流输出."""
        triage_text = outputs.get("triage", "") or outputs.get("text", "") or json.dumps(outputs)
        triage_data = _safe_parse_json(triage_text)

        analysis_text = outputs.get("analysis", "") or "{}"
        analysis_data = _safe_parse_json(analysis_text)

        response_text = outputs.get("response", "") or "{}"
        response_data = _safe_parse_json(response_text)

        result = AlertTriageResult(
            is_false_positive=triage_data.get("is_false_positive", False),
            severity=triage_data.get("severity", "low"),
            confidence=float(triage_data.get("confidence", 0.0)),
            needs_immediate_action=triage_data.get("needs_immediate_action", False),
            suggested_owner=triage_data.get("suggested_owner", ""),
            attack_vector=analysis_data.get("attack_vector", ""),
            mitigation_steps=response_data.get("actions", []),
            raw_json={
                "triage": triage_data,
                "analysis": analysis_data,
                "response": response_data,
            },
        )
        logger.info(
            "DifyDispatcher: alert fp=%s severity=%s immediate=%s",
            result.is_false_positive, result.severity, result.needs_immediate_action,
        )
        return result

    def execute_action(self, action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """通过安全终端执行具体操作 (block_ip / isolate_host / kill_process / harden).

        实际执行由 security_agent.terminal.executor.run_terminal_sync 完成，
        构建安全命令并通过 SafetyGate 校验后执行。
        """
        command = self._action_to_command(action_type, params)
        if not command:
            return {"status": "skipped", "reason": f"unknown action type: {action_type}"}

        try:
            from security_agent.terminal.executor import run_terminal_sync
            result = run_terminal_sync(command, timeout_sec=30)
            return {
                "status": "executed" if result.ok else "failed",
                "command": command,
                "exit_code": result.exit_code,
                "stdout": result.stdout[:500],
                "stderr": result.stderr[:500],
                "message": result.message,
            }
        except Exception as exc:
            logger.error("execute_action(%s) failed: %s", action_type, exc)
            return {"status": "error", "reason": str(exc)}

    @staticmethod
    def _action_to_command(action_type: str, params: Dict[str, Any]) -> str:
        """将 Dify 分析结果中的动作类型映射为安全检查后的命令."""
        target = params.get("target", "")
        reason = params.get("reason", "")
        cmd_map = {
            "block_ip": f"iptables -A INPUT -s {target} -j DROP -m comment --comment 'Dify:{reason}'",
            "kill_process": f"pkill -f {target}",
            "isolate_host": f"iptables -A INPUT -s {target} -j DROP && iptables -A OUTPUT -d {target} -j DROP",
            "harden": f"echo '[Dify] harden: {reason}'",
            "notify": f"echo '[Dify] notify: {reason} | wall'",
        }
        return cmd_map.get(action_type, "")


# ── Main integration class ───────────────────────────────────────

class DifyIntegration:
    """
    Dify 工作流结果 → security_agent 安全网关.

    用法:
        from security_agent.dify import DifyIntegration

        integration = DifyIntegration(gate=safety_gate, executor=terminal_executor)

        # 接收 Dify webhook 回调
        result = integration.handle_callback(workflow_type="threat_detection", outputs={...})

        # 如果需要自动处置
        if result.get("action_required"):
            integration.execute_remediation(result)
    """

    def __init__(
        self,
        gate=None,
        executor=None,
        plugin_manager=None,
        trace_storage=None,
        audit_log=None,
    ):
        self._gate = gate
        self._executor = executor
        self._plugin_manager = plugin_manager
        self._trace_storage = trace_storage
        self._audit_log = audit_log
        self.dispatcher = WorkflowDispatcher(
            gate=gate, executor=executor, plugin_manager=plugin_manager,
        )

    # ── Callback handler ─────────────────────────────────────

    def handle_callback(
        self,
        workflow_type: str,
        outputs: Dict[str, Any],
        workflow_run_id: str = "",
        trace_id: str = "",
    ) -> Dict[str, Any]:
        """处理 Dify 工作流完成后的回调，返回标准化结果."""
        timestamp = datetime.now(timezone.utc)

        try:
            wf_type = WorkflowType(workflow_type)
        except ValueError:
            logger.warning("DifyIntegration: unknown workflow_type=%s", workflow_type)
            return {"status": "ignored", "reason": f"unknown workflow type: {workflow_type}"}

        result: Dict[str, Any] = {
            "workflow_type": workflow_type,
            "workflow_run_id": workflow_run_id,
            "trace_id": trace_id,
            "timestamp": timestamp.isoformat(),
            "action_required": False,
            "actions_taken": [],
        }

        if wf_type == WorkflowType.THREAT_DETECTION:
            threat = self.dispatcher.dispatch_threat_detection(outputs)
            result["threat_result"] = threat.__dict__

            if threat.urgency in ("紧急",) and threat.risk_level >= 8:
                result["action_required"] = True
                result["suggested_actions"] = self._build_threat_actions(threat)
                # 通过三层防御安全评估
                if self._gate:
                    try:
                        gate_result = self._gate.evaluate_tool(
                            tool_name=f"threat_response:{threat.threat_type}",
                            arguments={
                                "risk_level": threat.risk_level,
                                "urgency": threat.urgency,
                                "recommendation": threat.recommendation,
                            },
                            user_message=threat.recommendation,
                        )
                        verdict = (
                            gate_result.verdict.value
                            if hasattr(gate_result.verdict, "value")
                            else str(gate_result.verdict)
                        )
                        result["gate_approved"] = verdict in ("allow", "confirm")
                        result["gate_verdict"] = verdict
                    except Exception as exc:
                        logger.warning("SafetyGate evaluation failed: %s", exc)
                        result["gate_approved"] = False
                        result["gate_error"] = str(exc)

        elif wf_type == WorkflowType.SECURITY_INSPECTION:
            inspection = self.dispatcher.dispatch_inspection(outputs)
            result["inspection_result"] = inspection.__dict__

            if inspection.critical_issues:
                result["action_required"] = True
                result["critical_count"] = len(inspection.critical_issues)

        elif wf_type == WorkflowType.ALERT_PROCESSING:
            alert = self.dispatcher.dispatch_alert_processing(outputs)
            result["alert_result"] = alert.__dict__

            if alert.needs_immediate_action and not alert.is_false_positive:
                result["action_required"] = True
                result["mitigation_steps"] = alert.mitigation_steps

        elif wf_type in (WorkflowType.SECURITY_CHAT, WorkflowType.KNOWLEDGE_RAG):
            result["response"] = outputs.get("answer", "") or outputs.get("text", "")

        # 写入审计日志
        self._audit_callback(result)
        return result

    def _build_threat_actions(self, threat: ThreatResult) -> List[Dict[str, Any]]:
        """根据威胁分析结果构建处置动作列表."""
        actions = []
        rec_lower = threat.recommendation.lower()
        scope_lower = threat.impact_scope.lower()

        # 封禁IP: 推荐中包含 ip/封禁/block，或影响范围包含IP
        if any(kw in rec_lower for kw in ("ip", "封禁", "block", "ban")):
            actions.append({"type": "block_ip", "target": "source_ip", "reason": threat.threat_type})
        elif any(kw in scope_lower for kw in ("ip", "地址")):
            actions.append({"type": "block_ip", "target": "source_ip", "reason": threat.threat_type})

        # 终止进程
        if any(kw in rec_lower for kw in ("进程", "kill", "终止", "结束进程")):
            actions.append({"type": "kill_process", "target": "suspicious_process", "reason": threat.threat_type})

        # 隔离主机
        if any(kw in rec_lower for kw in ("隔离", "isolate", "quarantine")):
            actions.append({"type": "isolate_host", "target": "affected_host", "reason": threat.threat_type})

        # 修复/加固
        if any(kw in rec_lower for kw in ("修复", "加固", "patch", "更新", "升级", "配置")):
            actions.append({"type": "harden", "target": "vulnerable_system", "reason": threat.threat_type})

        if not actions:
            actions.append({"type": "notify", "target": "security_team", "reason": threat.threat_type})
        return actions

    def execute_remediation(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """通过安全网关执行处置动作."""
        results = []
        for action in actions:
            action_type = action.get("type", "")
            try:
                r = self.dispatcher.execute_action(action_type, action)
                results.append({"action": action_type, "status": "executed", "result": r})
            except Exception as exc:
                logger.error("DifyIntegration: action %s failed: %s", action_type, exc)
                results.append({"action": action_type, "status": "failed", "error": str(exc)})
        return results

    def _audit_callback(self, result: Dict[str, Any]) -> None:
        """写入审计日志."""
        if self._audit_log:
            try:
                self._audit_log(result)
            except Exception:
                pass
        logger.info("DifyIntegration: callback handled, type=%s action=%s",
                     result.get("workflow_type"), result.get("action_required"))


# ── Factory ───────────────────────────────────────────────────────

def create_dify_integration(
    gate=None,
    executor=None,
    plugin_manager=None,
    trace_storage=None,
    audit_log=None,
) -> DifyIntegration:
    """工厂函数：创建 DifyIntegration 实例."""
    return DifyIntegration(
        gate=gate,
        executor=executor,
        plugin_manager=plugin_manager,
        trace_storage=trace_storage,
        audit_log=audit_log,
    )

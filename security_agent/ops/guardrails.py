"""企业级执行前守卫 — 预算、熔断、人工审批入队."""

from __future__ import annotations

from typing import Any

from security_agent.audit import log as audit
from security_agent.audit.trace import TraceContext
from security_agent.resilience.budget import BudgetExpiredError, get_request_budget
from security_agent.resilience.circuit import CircuitOpenError, get_circuit


def require_request_budget(slice_name: str = "executor") -> float:
    """耗尽预算时抛出 BudgetExpiredError，否则返回可用超时秒数."""
    budget = get_request_budget()
    if budget:
        budget.raise_if_expired()
        return budget.slice_timeout(slice_name)
    return 30.0


def check_mcp_tool_allowed(tool_name: str) -> None:
    """工具级 MCP 熔断（按工具名维度）."""
    from security_agent import config

    circuit = get_circuit(
        f"mcp:{tool_name}",
        failure_threshold=config.CIRCUIT_FAILURE_THRESHOLD,
        open_sec=config.CIRCUIT_OPEN_SEC,
    )
    if not circuit.allow():
        raise CircuitOpenError(f"工具熔断中: {tool_name}（请稍后重试或换用 Skill Flow）")


def record_tool_success(tool_name: str) -> None:
    get_circuit(f"mcp:{tool_name}").record_success()


def record_tool_failure(tool_name: str, error: str) -> None:
    get_circuit(f"mcp:{tool_name}").record_failure(error)


def enqueue_human_approval(
    *,
    trace_id: str,
    user_message: str,
    action_description: str,
    risk_level: str,
    verdict: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """S4：写入持久化审批队列."""
    from security_agent.confirm import ConfirmationLevel, get_confirmation_manager

    level = ConfirmationLevel.APPROVE
    if verdict in ("escalate", "quarantine"):
        level = ConfirmationLevel.ESCALATE

    mgr = get_confirmation_manager()
    req = mgr.create_request(
        trace_id=trace_id or TraceContext.current_trace_id(),
        user_message=user_message[:500],
        action_description=action_description[:500],
        risk_level=risk_level,
        confirmation_level=level,
        metadata=metadata or {},
    )
    audit.append_audit(
        "approval_enqueued",
        {
            "request_id": req.request_id,
            "trace_id": req.trace_id,
            "verdict": verdict,
            "risk_level": risk_level,
        },
        level="warning",
    )
    return {
        "confirmation_request_id": req.request_id,
        "status": req.status.value,
        "expires_at": req.metadata.get("expires_at"),
        "degradation_level": "S4",
    }


def is_approval_granted(request_id: str, *, command: str = "") -> bool:
    """执行前校验：审批单已批准且未超时."""
    from security_agent.confirm import ConfirmationStatus, get_confirmation_manager

    mgr = get_confirmation_manager()
    mgr.expire_stale_requests()
    req = mgr.get_request(request_id)
    if not req or req.status != ConfirmationStatus.APPROVED:
        return False
    if command and req.metadata.get("command") and req.metadata.get("command") != command:
        return False
    return True

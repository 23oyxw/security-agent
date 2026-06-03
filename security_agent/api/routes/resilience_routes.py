"""弹性能力状态 — 熔断器与请求预算（运维可观测）."""

from fastapi import APIRouter, Depends

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User
from security_agent.resilience.budget import get_request_budget
from security_agent.resilience.circuit import list_circuit_states, reset_circuit, reset_circuits_prefix

router = APIRouter()


@router.get("/status")
async def resilience_status(user: User = Depends(get_current_user)):
    budget = get_request_budget()
    return {
        "circuits": list_circuit_states(),
        "active_budget": budget.to_dict() if budget else None,
    }


@router.post("/circuits/reset")
async def reset_circuits(
    user: User = Depends(get_current_user),
    name: str | None = None,
    prefix: str = "llm:",
):
    """重置熔断器（默认清空所有 llm:*，修复模型配置后调用）."""
    if name:
        ok = reset_circuit(name)
        return {"ok": ok, "name": name}
    n = reset_circuits_prefix(prefix)
    return {"ok": True, "reset_count": n, "prefix": prefix}

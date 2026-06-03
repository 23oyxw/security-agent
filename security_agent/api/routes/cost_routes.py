"""成本路由"""

from fastapi import APIRouter, Depends
from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()


@router.get("/summary")
async def cost_summary(days: int = 7, user: User = Depends(get_current_user)):
    """成本汇总"""
    try:
        from security_agent.agent.cost import CostTracker
        tracker = CostTracker()
        return tracker.summary(days=days) if hasattr(tracker, "summary") else {"total_cost_usd": 0, "total_tokens": 0, "period_days": days}
    except Exception:
        return {"total_cost_usd": 0, "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "model": "unknown", "period_days": days}
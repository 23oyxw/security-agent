"""审计路由"""

from fastapi import APIRouter, Depends
from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()


@router.get("/logs")
async def audit_logs(limit: int = 50, user: User = Depends(get_current_user)):
    """审计日志"""
    try:
        from security_agent.audit.log import get_audit_logs
        return {"logs": get_audit_logs(limit=limit), "total": 0}
    except Exception:
        return {"logs": [], "total": 0}
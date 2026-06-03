"""管理路由"""

from fastapi import APIRouter, Depends
from security_agent.api.deps import require_admin
from security_agent.auth.models import User

router = APIRouter()


@router.get("/config")
async def get_config(user: User = Depends(require_admin)):
    """获取系统配置"""
    return {"status": "ok", "config": {}}


@router.get("/system-info")
async def system_info(user: User = Depends(require_admin)):
    """系统信息"""
    import platform
    return {
        "hostname": platform.node(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "arch": platform.machine(),
    }
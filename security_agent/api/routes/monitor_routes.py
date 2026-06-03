"""监控路由"""

import os
import time
import subprocess
from fastapi import APIRouter, Depends
from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()
_START_TIME = time.time()


@router.get("/status")
async def system_status(user: User = Depends(get_current_user)):
    """系统状态"""
    try:
        import psutil
        return {
            "uptime": time.time() - _START_TIME,
            "cpu": psutil.cpu_percent(interval=0.3),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage("/").percent,
            "process_count": len(psutil.pids()),
        }
    except Exception:
        return {"uptime": time.time() - _START_TIME, "cpu": 0, "memory": 0, "disk": 0}


@router.get("/services")
async def service_status(user: User = Depends(get_current_user)):
    """服务状态"""
    services = {}
    for svc in ["litellm", "security-agent", "streamlit"]:
        try:
            r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=3)
            services[svc] = r.stdout.strip()
        except Exception:
            services[svc] = "unknown"
    return {"services": services}
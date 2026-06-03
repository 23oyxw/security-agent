"""② MCP 插件化路由"""

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from security_agent.api.deps import get_current_user, require_operator
from security_agent.api.mcp_host import get_mcp_host
from security_agent.auth.models import User
from security_agent.mcp.registry import get_mcp_registry

router = APIRouter()


class McpRegisterRequest(BaseModel):
    name: str
    command: str = ""
    protocol: str = "stdio"
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "running"


@router.get("/servers")
async def list_servers(user: User = Depends(get_current_user)):
    """列出所有 MCP 服务器"""
    return {"servers": get_mcp_host().list_servers()}


@router.get("/tools")
async def list_tools(user: User = Depends(get_current_user)):
    """列出所有 MCP 工具"""
    return {"tools": get_mcp_host().get_all_tools()}


@router.post("/health")
async def health_check_all(user: User = Depends(get_current_user)):
    """全部健康检查"""
    return {"results": get_mcp_host().health_check_all(), "checked_at": time.time()}


@router.post("/servers/{name}/health")
async def health_check_server(name: str, user: User = Depends(get_current_user)):
    """单个 MCP 服务健康检查（更新 last_health_check）"""
    result = get_mcp_host().health_check(name)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="MCP 服务器未找到")
    return result


@router.get("/servers/{name}")
async def get_server(name: str, user: User = Depends(get_current_user)):
    """获取单个服务器详情"""
    srv = get_mcp_host().get_server(name)
    if not srv:
        raise HTTPException(status_code=404, detail="MCP 服务器未找到")
    return srv


@router.post("/reload")
async def reload_mcp(user: User = Depends(require_operator)):
    """热插拔：重新发现 Skill 并刷新 MCP 服务列表."""
    return get_mcp_registry().reload()


@router.get("/manifest")
async def get_manifest(user: User = Depends(get_current_user)):
    """读取持久化的 manifest 配置."""
    return {"servers": get_mcp_registry().list_manifest()}


@router.post("/servers/register")
async def register_server(req: McpRegisterRequest, user: User = Depends(require_operator)):
    """注册或更新 MCP 服务（写入 manifest）."""
    srv = get_mcp_registry().register_server(
        req.name,
        command=req.command,
        protocol=req.protocol,
        tools=req.tools,
        status=req.status,
    )
    return {"ok": True, "server": srv}


@router.delete("/servers/{name}")
async def unregister_server(name: str, user: User = Depends(require_operator)):
    """从 Host 与 manifest 移除 MCP 服务."""
    ok = get_mcp_registry().unregister_server(name)
    if not ok:
        raise HTTPException(status_code=404, detail="MCP 服务器未找到")
    return {"ok": True, "name": name}
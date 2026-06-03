"""FastAPI 依赖注入"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from security_agent.auth.jwt_utils import decode_access_token
from security_agent.auth.store import get_user_store
from security_agent.auth.models import User

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> User:
    """从 JWT token 获取当前用户"""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的 token",
        )
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 token payload",
        )
    user = get_user_store().get_user(username)
    if user is None or user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user


async def require_operator(user: User = Depends(get_current_user)) -> User:
    """要求操作员或管理员权限"""
    if user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要操作员或管理员权限",
        )
    return user
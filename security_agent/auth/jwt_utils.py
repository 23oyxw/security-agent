"""JWT 工具"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import jwt

from security_agent.config import JWT_EXPIRE_HOURS, JWT_SECRET

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = JWT_EXPIRE_HOURS


def create_access_token(
    data: Dict[str, Any],
    expires_hours: Optional[int] = None,
) -> str:
    """创建 JWT access token"""
    payload = data.copy()
    expire = time.time() + (expires_hours or ACCESS_TOKEN_EXPIRE_HOURS) * 3600
    payload.update({"exp": expire, "iat": time.time()})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """解码 JWT token, 失败返回 None"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

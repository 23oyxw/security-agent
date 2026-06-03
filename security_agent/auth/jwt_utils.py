"""JWT 工具"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import jwt

# 密钥: 优先从环境变量读取, 否则随机生成
_JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not _JWT_SECRET:
    _JWT_SECRET = os.urandom(32).hex()

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "8"))


def create_access_token(
    data: Dict[str, Any],
    expires_hours: Optional[int] = None,
) -> str:
    """创建 JWT access token"""
    payload = data.copy()
    expire = time.time() + (expires_hours or ACCESS_TOKEN_EXPIRE_HOURS) * 3600
    payload.update({"exp": expire, "iat": time.time()})
    return jwt.encode(payload, _JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """解码 JWT token, 失败返回 None"""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
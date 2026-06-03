"""认证数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import time


@dataclass
class User:
    """用户模型"""
    username: str
    hashed_password: str
    role: str = "viewer"  # admin / operator / viewer
    display_name: str = ""
    email: str = ""
    disabled: bool = False
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None

    def to_safe_dict(self) -> dict:
        """返回不含密码的用户信息"""
        return {
            "username": self.username,
            "role": self.role,
            "display_name": self.display_name or self.username,
            "email": self.email,
            "disabled": self.disabled,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }


@dataclass
class Role:
    """角色定义"""
    name: str
    permissions: List[str] = field(default_factory=list)
    description: str = ""


# 预定义角色
ROLES = {
    "admin": Role(
        name="admin",
        permissions=["read", "write", "execute", "approve", "manage_users", "view_audit", "mcp_manage"],
        description="系统管理员，拥有所有权限",
    ),
    "operator": Role(
        name="operator",
        permissions=["read", "write", "execute", "view_audit"],
        description="运维操作员，可执行操作但需审批",
    ),
    "viewer": Role(
        name="viewer",
        permissions=["read", "view_audit"],
        description="只读用户，仅查看",
    ),
}
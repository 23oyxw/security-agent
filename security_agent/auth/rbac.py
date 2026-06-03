"""RBAC 权限检查"""

from __future__ import annotations

from typing import List

from security_agent.auth.models import ROLES

# 角色 → 权限映射（从 models.ROLES 提取）
ROLE_PERMISSIONS = {name: role.permissions for name, role in ROLES.items()}


def check_permission(role: str, permission: str) -> bool:
    """检查角色是否拥有指定权限"""
    perms = ROLE_PERMISSIONS.get(role, [])
    return permission in perms


def require_permissions(role: str, permissions: List[str]) -> List[str]:
    """返回角色缺失的权限列表（空 = 全部通过）"""
    perms = set(ROLE_PERMISSIONS.get(role, []))
    return [p for p in permissions if p not in perms]
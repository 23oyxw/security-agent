"""认证路由"""

from fastapi import APIRouter, Depends, HTTPException, status
from security_agent.api.models import LoginRequest, TokenResponse, UserCreate, UserResponse
from security_agent.api.deps import get_current_user, require_admin
from security_agent.auth.store import get_user_store
from security_agent.auth.jwt_utils import create_access_token
from security_agent.auth.models import User

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """登录"""
    store = get_user_store()
    if not store.verify_password(req.username, req.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    user = store.get_user(req.username)
    store.update_last_login(req.username)
    token = create_access_token({"sub": req.username, "role": user.role})
    return TokenResponse(access_token=token, role=user.role, username=req.username)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """当前用户信息"""
    return UserResponse(**user.to_safe_dict())


@router.get("/users", response_model=list[UserResponse])
async def list_users(user: User = Depends(require_admin)):
    """列出所有用户（管理员）"""
    return [UserResponse(**u.to_safe_dict()) for u in get_user_store().list_users()]


@router.post("/users", response_model=UserResponse)
async def create_user(req: UserCreate, user: User = Depends(require_admin)):
    """创建用户（管理员）"""
    store = get_user_store()
    if store.get_user(req.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    new_user = store.create_user(req.username, req.password, req.role, req.display_name, req.email)
    return UserResponse(**new_user.to_safe_dict())


@router.delete("/users/{username}")
async def delete_user(username: str, user: User = Depends(require_admin)):
    """删除用户（管理员）"""
    if username == user.username:
        raise HTTPException(status_code=400, detail="不能删除自己")
    if get_user_store().delete_user(username):
        return {"ok": True}
    raise HTTPException(status_code=404, detail="用户不存在")
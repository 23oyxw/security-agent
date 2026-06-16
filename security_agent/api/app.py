"""FastAPI 主应用 — 包装现有模块，提供 REST API + 静态文件服务"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

from security_agent.version import __version__

from security_agent.api.routes import (
    auth_routes,
    perception_routes,
    safety_routes,
    executor_routes,
    trace_routes,
    agent_routes,
    knowledge_routes,
    alert_routes,
    cost_routes,
    monitor_routes,
    mcp_routes,
    report_routes,
    admin_routes,
    audit_routes,
    skill_flow_routes,
    workflow_routes,
    chat_ws_routes,
    resilience_routes,
    ops_routes,
    metrics_routes,
    eval_routes,
    l5_routes,
    l1_routes,
    repair_routes,
    inspection_routes,
)

_START_TIME = time.time()

# ---- 速率限制器（slowapi）----
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app = FastAPI(
    title="银河麒麟智能安全运维 Agent",
    description="多维感知 + 推理决策 + 安全控制",
    version=__version__,
)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"请求过于频繁，请稍后重试（限 {exc.detail}）"},
    )

# CORS — 允许前端 dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（按五大支柱组织）
app.include_router(auth_routes.router,      prefix="/api/auth",      tags=["认证"])
app.include_router(perception_routes.router, prefix="/api/perception", tags=["① 多维感知"])
app.include_router(mcp_routes.router,       prefix="/api/mcp",       tags=["② MCP插件化"])
app.include_router(safety_routes.router,    prefix="/api/safety",    tags=["③ 安全意图校验"])
app.include_router(executor_routes.router,  prefix="/api/executor",  tags=["④ 最小权限执行"])
app.include_router(trace_routes.router,     prefix="/api/trace",     tags=["⑤ 推理链路溯源"])
app.include_router(agent_routes.router,     prefix="/api/agent",     tags=["Agent 对话"])
app.include_router(l1_routes.router,        prefix="/api/l1",        tags=["L1 三感知"])
app.include_router(knowledge_routes.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(alert_routes.router,     prefix="/api/alerts",    tags=["告警"])
app.include_router(cost_routes.router,      prefix="/api/cost",      tags=["成本"])
app.include_router(monitor_routes.router,   prefix="/api/monitor",   tags=["监控"])
app.include_router(report_routes.router,    prefix="/api/reports",   tags=["报告"])
app.include_router(admin_routes.router,     prefix="/api/admin",     tags=["管理"])
app.include_router(audit_routes.router,     prefix="/api/audit",     tags=["审计"])
app.include_router(skill_flow_routes.router, prefix="/api/skills/flows", tags=["Skill Flow"])
app.include_router(workflow_routes.router,   prefix="/api/workflow",     tags=["工作流"])
app.include_router(chat_ws_routes.router,     prefix="/api/agent",        tags=["WebSocket 实时聊天"])
app.include_router(resilience_routes.router,  prefix="/api/resilience",   tags=["弹性"])
app.include_router(ops_routes.router,         prefix="/api/ops",          tags=["运维操作"])
app.include_router(metrics_routes.router,     prefix="",                  tags=["监控指标"])
app.include_router(eval_routes.router,         prefix="/api/eval",         tags=["Agent 评估"])
app.include_router(l5_routes.router,           prefix="/api/l5",           tags=["L5 链路分析"])
app.include_router(repair_routes.router,       prefix="/api/repair",       tags=["环境修复"])
app.include_router(inspection_routes.router,   prefix="/api/inspection",   tags=["巡检引擎"])

# 健康检查（无需认证）
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "uptime": round(time.time() - _START_TIME, 2),
        "modules": {
            "智能 Agent 引擎": "active",
            "安全门禁(三层防御)": "active",
            "审计日志(事件脊柱)": "active",
            "监控服务(动态阈值)": "active",
            "知识库(Playbook+Wiki)": "active",
            "MCP 热插拔(17 Skills)": "active",
            "WebSocket 流式": "active",
            "全链路 Trace": "active",
            "弹性熔断降级": "active",
            "华测式巡检引擎": "active",
            "可插拔 Webhook": "active",
            "S4 人工审批": "active",
        },
    }


@app.get("/api/health/ready")
async def health_ready():
    """企业级就绪探针 — 依赖可用性 + 熔断概览."""
    checks: dict = {"status": "ok", "checks": {}}
    try:
        from security_agent.confirm import get_confirmation_manager

        mgr = get_confirmation_manager()
        expired = mgr.expire_stale_requests()
        checks["checks"]["confirmations"] = {"ok": True, "expired": expired}
    except Exception as exc:
        checks["checks"]["confirmations"] = {"ok": False, "error": str(exc)}
        checks["status"] = "degraded"

    try:
        from security_agent.storage.trace_storage import get_trace_storage

        get_trace_storage()
        checks["checks"]["trace_storage"] = {"ok": True}
    except Exception as exc:
        checks["checks"]["trace_storage"] = {"ok": False, "error": str(exc)}
        checks["status"] = "degraded"

    try:
        from security_agent.resilience.circuit import list_circuit_states

        open_circuits = [c for c in list_circuit_states() if c.get("state") == "open"]
        checks["checks"]["circuits"] = {"ok": len(open_circuits) == 0, "open": open_circuits}
        if open_circuits:
            checks["status"] = "degraded"
    except Exception as exc:
        checks["checks"]["circuits"] = {"ok": False, "error": str(exc)}

    return checks

# ---- 启动时初始化默认用户 ----
@app.on_event("startup")
async def _ensure_admin():
    """若数据库无 admin 用户则自动创建"""
    from security_agent.auth.store import get_user_store
    store = get_user_store()
    if not store.get_user("admin"):
        store.create_user("admin", "admin123", role="admin", display_name="管理员")
        logger.info("已创建默认管理员: admin / admin123")
    try:
        from security_agent.confirm import get_confirmation_manager

        n = get_confirmation_manager().expire_stale_requests()
        if n:
            logger.info("已清理超时审批单: %s", n)
    except Exception as exc:
        logger.warning("审批队列初始化: %s", exc)
    try:
        from security_agent.resilience.circuit import reset_circuits_prefix

        n = reset_circuits_prefix("llm:")
        if n:
            logger.info("已重置 LLM 熔断器: %s 个", n)
    except Exception as exc:
        logger.warning("熔断器初始化: %s", exc)
    try:
        from security_agent import config

        logger.info(
            "LLM 路由: model=%s proxy=%s base=%s",
            config.resolve_agent_model(),
            config.using_litellm_proxy(),
            (config.LLM_BASE_URL or "")[:48],
        )
    except Exception as exc:
        logger.warning("LLM 配置日志: %s", exc)


# ---- 根路径与 Vue SPA 静态托管 ----
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if _frontend_dist.is_dir():
    from fastapi.responses import FileResponse
    from fastapi import HTTPException

    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir), html=False), name="assets")

    @app.get("/")
    async def spa_index():
        return FileResponse(
            _frontend_dist / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api") or full_path in ("docs", "redoc", "openapi.json"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(
            _frontend_dist / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
else:
    @app.get("/")
    async def root():
        return RedirectResponse(url="/docs")

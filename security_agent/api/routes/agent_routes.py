"""Agent 对话路由 — L1 plan / L3 execute / 兼容 chat"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from security_agent.api.deps import get_current_user
from security_agent.api.chat_payload import build_chat_payload
from security_agent.api.models import (
    ChatRequest,
    ChatResponse,
    PlanRequest,
    AnalysisPlanResponse,
    ExecutePlanRequest,
    L2PrecheckRequest,
    OrchestrateRequest,
    OrchestrateResponse,
    AgentStageStatus,
)
from security_agent.auth.models import User

router = APIRouter()


@router.get("/registry")
async def agent_registry(user: User = Depends(get_current_user)):
    """三代 Agent + 工具簇 + 编排元数据（与前端 constants/agents.js 对齐）"""
    from security_agent.agent.agent_registry import (
        AGENT_REGISTRY,
        ORCHESTRATOR,
        TOOL_CLUSTERS,
        PIPELINE_LAYERS,
    )

    return {
        "orchestrator": ORCHESTRATOR,
        "agents": AGENT_REGISTRY,
        "tool_clusters": TOOL_CLUSTERS,
        "pipeline_layers": PIPELINE_LAYERS,
    }


@router.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: OrchestrateRequest, user: User = Depends(get_current_user)):
    """编排：核心调度(analyze) → 安全沙箱 → [execute] → 审计迭代."""
    from security_agent.agent.core_agents import (
        audit_iteration_agent,
        core_dispatch_agent,
        safety_sandbox_agent,
    )
    from security_agent.api.agent_plan import get_plan, execute_plan

    agents: list[AgentStageStatus] = [
        AgentStageStatus(
            agent="core_dispatch",
            display_name="核心调度代理",
            layer="L1+L3",
            status="running",
            detail="analyze 阶段",
        ),
        AgentStageStatus(
            agent="safety_sandbox",
            display_name="安全防护沙箱代理",
            layer="L2",
            status="idle",
        ),
        AgentStageStatus(
            agent="audit_iteration",
            display_name="审计迭代代理",
            layer="L4+L5",
            status="idle",
        ),
    ]

    audit_summary = None
    execute_payload = None

    try:
        plan = await core_dispatch_agent.analyze_phase(req.message, batch_id=req.batch_id)
        agents[0].status = "done"
        agents[0].detail = f"L1 analyze · 意图 {plan.get('intent')}"

        agents[1].status = "running"
        l2 = await safety_sandbox_agent.precheck(plan["plan_id"])
        verdict = l2.get("verdict", "pass")
        if verdict == "deny":
            agents[1].status = "blocked"
            agents[1].detail = "L2 拒绝"
        elif verdict == "confirm":
            agents[1].status = "done"
            agents[1].detail = "需二次确认"
        else:
            agents[1].status = "done"
            agents[1].detail = "L2 通过"

        plan = get_plan(plan["plan_id"]) or plan

        if req.auto_execute and verdict != "deny":
            needs_confirm = bool(plan.get("requires_confirm")) or verdict == "confirm"
            if not needs_confirm or req.user_confirmed:
                agents[0].status = "running"
                agents[0].detail = "execute 阶段"
                execute_payload = await execute_plan(
                    plan["plan_id"],
                    session_id=plan.get("trace_id"),
                    user_confirmed=req.user_confirmed,
                )
                plan = get_plan(plan["plan_id"]) or plan
                agents[0].status = "done"
                agents[0].detail = "L3 execute 完成"
                audit_summary = execute_payload.get("audit")
                if audit_summary:
                    agents[2].status = "done"
                    agents[2].detail = f"trace {str(audit_summary.get('trace_id', ''))[:8]}"
            else:
                agents[0].detail = "awaiting execute 阶段锁"
        else:
            agents[2].status = "running"
            agents[2].detail = "plan 快照 L4/L5"
            audit_summary = await audit_iteration_agent.finalize_plan_snapshot(plan, l2_result=l2)
            agents[2].status = "done"
            agents[2].detail = f"plan {str(plan.get('plan_id', ''))[:8]}"

        return OrchestrateResponse(
            plan=AnalysisPlanResponse(**plan),
            l2=l2,
            agents=agents,
            execute=ChatResponse(**execute_payload) if execute_payload else None,
            audit=audit_summary,
        )
    except Exception as e:
        for a in agents:
            if a.status == "running":
                a.status = "error"
                a.detail = str(e)[:200]
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan", response_model=AnalysisPlanResponse)
async def create_plan(req: PlanRequest, user: User = Depends(get_current_user)):
    """L1 分析计划 — 并行边界感知、知识检索、静态感知，不执行写操作"""
    from security_agent.api.agent_plan import build_analysis_plan

    plan = await build_analysis_plan(req.message, batch_id=req.batch_id)
    return AnalysisPlanResponse(**plan)


@router.post("/l2/precheck")
async def l2_precheck(req: L2PrecheckRequest, user: User = Depends(get_current_user)):
    """L2 安全管控预检"""
    from security_agent.api.agent_plan import run_l2_precheck

    try:
        return await run_l2_precheck(req.plan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="plan_id 不存在")


@router.post("/execute", response_model=ChatResponse)
async def execute_plan_route(req: ExecutePlanRequest, user: User = Depends(get_current_user)):
    """L3 推理分发执行 — 需有效 plan_id，先分析后执行"""
    from security_agent.api.agent_plan import execute_plan

    try:
        payload = await execute_plan(
            req.plan_id,
            session_id=req.session_id,
            user_confirmed=req.user_confirmed,
        )
        return ChatResponse(**payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="plan_id 不存在")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/plan/{plan_id}", response_model=AnalysisPlanResponse)
async def get_plan_route(plan_id: str, user: User = Depends(get_current_user)):
    from security_agent.api.agent_plan import get_plan

    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="plan_id 不存在")
    return AnalysisPlanResponse(**plan)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user: User = Depends(get_current_user)):
    """遗留直连 — 绕过五层闸门，仅调试。生产请用 /orchestrate。"""
    session_id = req.session_id or str(uuid.uuid4())[:8]
    try:
        from security_agent.agent.brain import AgentBrain
        brain = AgentBrain(session_id=session_id)
        result = await brain.chat(req.message)
        payload = build_chat_payload(result, session_id)
        payload["reply"] = (
            "[警告：未走五层流水线] "
            + (payload.get("reply") or "")
            + "\n\n请使用：计划模式 L1 三感知 → L2 防护 → 执行模式 L3。"
        )
        return ChatResponse(**payload)
    except Exception as e:
        return ChatResponse(
            reply=f"[降级] 无法调用 Agent 引擎: {e}",
            session_id=session_id,
        )

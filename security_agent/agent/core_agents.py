"""三代智能体 — 终版架构实现.

1. core_dispatch   — L1 analyze + L3 execute（阶段锁，同一 Agent）
2. safety_sandbox  — L2 独立安全闸门
3. audit_iteration — L4 审计溯源 + L5 数学模型迭代
"""

from __future__ import annotations

from typing import Any, Optional

from security_agent.api.chat_payload import build_chat_payload


class CoreDispatchAgent:
    """核心调度代理：L1 分析阶段 + L3 执行阶段（阶段锁）."""

    agent_id = "core_dispatch"
    display_name = "核心调度代理"
    layers = "L1+L3"
    PHASE_ANALYZE = "analyze"
    PHASE_EXECUTE = "execute"

    async def analyze_phase(
        self,
        message: str,
        *,
        batch_id: Optional[str] = None,
    ) -> dict[str, Any]:
        from security_agent.api.agent_plan import build_analysis_plan

        plan = await build_analysis_plan(message, batch_id=batch_id)
        plan["agent"] = self.agent_id
        plan["phase"] = self.PHASE_ANALYZE
        plan["phase_lock"] = "L1_only"
        return plan

    async def execute_phase(
        self,
        plan: dict[str, Any],
        *,
        session_id: Optional[str] = None,
        user_confirmed: bool = False,
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        from security_agent.pipeline.trace_id import normalize_trace_id

        plan_id = plan.get("plan_id") or ""
        tid = normalize_trace_id(trace_id or session_id or plan.get("trace_id") or plan_id)
        msg = plan.get("user_message_resolved") or plan.get("message") or ""

        exec_plan = {
            "intent": plan.get("intent", "general"),
            "tool_chain": plan.get("tool_chain") or [],
            "tool_args": plan.get("tool_args") or {},
            "skill_flow": plan.get("skill_flow"),
            "use_llm_tools": plan.get("use_llm_tools", False),
            "hint": plan.get("hint") or "",
            "user_message_resolved": msg,
            "trace_id": tid,
        }

        from security_agent.agent.brain import AgentBrain

        brain = AgentBrain(session_id=tid, user_confirmed=user_confirmed)
        result = await brain.chat(msg, plan=exec_plan, trace_id=tid)
        payload = build_chat_payload(result, tid)
        payload["plan_id"] = plan_id
        payload["agent"] = self.agent_id
        payload["phase"] = self.PHASE_EXECUTE
        payload["trace_id"] = normalize_trace_id(result.get("trace_id") or tid)
        return payload


class SafetySandboxAgent:
    """安全防护沙箱代理：L2 只校验不执行."""

    agent_id = "safety_sandbox"
    display_name = "安全防护沙箱代理"
    layers = "L2"

    async def precheck(self, plan_id: str) -> dict[str, Any]:
        from security_agent.api.agent_plan import run_l2_precheck

        result = await run_l2_precheck(plan_id)
        result["agent"] = self.agent_id
        return result


class AuditIterationAgent:
    """审计溯源 & 数学模型迭代代理：L4 + L5."""

    agent_id = "audit_iteration"
    display_name = "审计迭代代理"
    layers = "L4+L5"

    async def finalize(
        self,
        plan: dict[str, Any],
        *,
        execute_result: Optional[dict[str, Any]] = None,
        l2_result: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        from security_agent.pipeline.trace_id import normalize_trace_id

        trace_id = normalize_trace_id(
            (execute_result or {}).get("trace_id") or plan.get("trace_id") or plan.get("plan_id")
        )
        tools = (execute_result or {}).get("tools_used") or []
        summary = {
            "agent": self.agent_id,
            "trace_id": trace_id,
            "plan_id": plan.get("plan_id"),
            "audit_status": "recorded",
            "l2_verdict": (l2_result or {}).get("verdict") or plan.get("l2_verdict"),
            "tools_invoked": len(tools),
            "wiki_reflux": "pending",
            "metrics_snapshot": {
                "intent": plan.get("intent"),
                "batch_id": plan.get("batch_id"),
                "degradation": (execute_result or {}).get("degradation_level"),
            },
            "charts": {
                "static_perception": "L1",
                "link_trace": "L4",
                "global_metrics": "L5",
            },
        }
        try:
            from security_agent.audit import log as audit

            audit.append_audit(
                "audit_iteration_finalize",
                {
                    "trace_id": trace_id,
                    "plan_id": plan.get("plan_id"),
                    "tools": tools[:20],
                },
            )
        except Exception:
            pass
        try:
            from security_agent.pipeline.coordination import record_l4_finalize, record_l5_analytics

            record_l4_finalize(plan, summary)
            record_l5_analytics(plan, summary)
        except Exception:
            pass
        return summary


core_dispatch_agent = CoreDispatchAgent()
safety_sandbox_agent = SafetySandboxAgent()
audit_iteration_agent = AuditIterationAgent()

# 兼容旧 ID（deprecated）
plan_perception_agent = core_dispatch_agent
safety_agent = safety_sandbox_agent
execute_agent = core_dispatch_agent

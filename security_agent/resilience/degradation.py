"""降级阶梯 S0–S4：模型全挂时走 L2 flow / Playbook 模板."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from security_agent.retrieval.hybrid import format_grounding_block, search_knowledge


class DegradationLevel(str, Enum):
    S0_FULL = "S0"       # LLM + 工具 + RAG
    S1_MODEL_FB = "S1"   # 备用模型
    S2_RULE = "S2"       # Skill flow / 规则 + Playbook
    S3_READONLY = "S3"   # 仅诊断，禁止执行
    S4_HUMAN = "S4"      # 待人工


async def try_rule_fallback(
    user_message: str,
    *,
    plan: dict[str, Any] | None = None,
    trace_id: str = "",
) -> dict[str, Any] | None:
    """S2：无 LLM 时的确定性兜底。成功返回与 chat() 兼容的 dict."""
    from security_agent.agent.orchestrator import (
        INTENT_SKILL_FLOWS,
        build_plan,
        build_skill_flow_context,
        detect_intent,
    )

    plan = plan or build_plan(user_message)
    flow = plan.get("skill_flow") or INTENT_SKILL_FLOWS.get(plan.get("intent", ""))

    if flow:
        from security_agent.skills.flows import run_skill_flow

        ctx = build_skill_flow_context(flow, user_message)
        result = await run_skill_flow(flow, ctx)
        reply = _format_flow_reply(flow, result)
        return {
            "reply": reply,
            "tool_trace": [{"skill_flow": flow, "degraded": True, "result": result}],
            "plan": plan,
            "auto_warn": not result.get("ok"),
            "citations": [],
            "token_usage": {},
            "model_used": "rule_fallback",
            "fallback_used": True,
            "degradation_level": DegradationLevel.S2_RULE.value,
            "trace_id": trace_id or result.get("trace_id", ""),
        }

    hits = search_knowledge(user_message, top_k=5)
    if not hits:
        return None

    grounding = format_grounding_block(hits)
    cites = ", ".join(f"[{h['id']}]" for h in hits[:3])
    reply = (
        f"【规则模式 · 未调用大模型】trace: {trace_id or '—'}\n"
        f"意图: {plan.get('intent', detect_intent(user_message))}\n\n"
        f"{grounding}\n"
        f"请依据上述 Playbook 编号 {cites} 处理；如需自动执行请改用 Skill 流程或重新连接模型。"
    )
    return {
        "reply": reply,
        "tool_trace": [{"degraded": True, "knowledge_hits": len(hits)}],
        "plan": plan,
        "auto_warn": False,
        "citations": hits[:3],
        "token_usage": {},
        "model_used": "playbook_only",
        "fallback_used": True,
        "degradation_level": DegradationLevel.S2_RULE.value,
        "trace_id": trace_id,
    }


def _format_flow_reply(flow_name: str, result: dict[str, Any]) -> str:
    from security_agent.agent.skill_flow_format import format_skill_flow_reply

    text = format_skill_flow_reply(flow_name, result)
    title = result.get("display_name") or flow_name
    return text.replace(f"【{title}】", f"【{title}·规则兜底】", 1)

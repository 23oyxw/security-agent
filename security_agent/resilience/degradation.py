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
    tool_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """S2：无 LLM 时的确定性兜底。成功返回与 chat() 兼容的 dict."""
    from security_agent.agent.health_format import format_tool_outputs_for_user
    from security_agent.agent.orchestrator import (
        INTENT_SKILL_FLOWS,
        build_plan,
        build_skill_flow_context,
        detect_intent,
    )

    plan = plan or build_plan(user_message)
    intent = plan.get("intent", detect_intent(user_message))

    if tool_trace:
        formatted = format_tool_outputs_for_user(
            intent,
            tool_trace=tool_trace,
            trace_id=trace_id,
            degraded=True,
        )
        if formatted:
            return {
                "reply": formatted,
                "tool_trace": tool_trace + [{"degraded": True, "formatted": True}],
                "plan": plan,
                "auto_warn": False,
                "citations": [],
                "token_usage": {},
                "model_used": "tool_fallback",
                "fallback_used": True,
                "degradation_level": DegradationLevel.S2_RULE.value,
                "trace_id": trace_id,
            }

    tool_fb = await _try_tool_chain_fallback(plan, trace_id)
    if tool_fb:
        return tool_fb

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

    cites = ", ".join(f"[{h['id']}]" for h in hits[:3])
    reply = (
        f"【离线提示】大模型暂不可用，未能自动采集系统指标。\n"
        f"意图: {intent} · trace: {trace_id or '—'}\n\n"
        f"相关 Playbook: {cites}\n"
        f"建议：使用「查看系统健康」类指令触发本地工具；或检查 .env 中 LLM 配置后重试。"
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


async def _try_tool_chain_fallback(
    plan: dict[str, Any],
    trace_id: str,
) -> dict[str, Any] | None:
    """按计划中的只读 tool_chain 直接采集数据，无需 LLM."""
    import json

    from security_agent.agent.parallel import PARALLEL_SAFE_TOOLS, run_tools_parallel

    chain = plan.get("tool_chain") or []
    readonly = [t for t in chain if t in PARALLEL_SAFE_TOOLS]
    if not readonly:
        return None

    tool_calls = [(name, {}) for name in readonly]
    result = await run_tools_parallel(tool_calls, max_concurrency=len(tool_calls))
    if result.get("errors") and not result.get("results"):
        return None

    blocks: list[str] = []
    for name in readonly:
        payload = result.get("results", {}).get(name)
        if payload is None:
            continue
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if len(text) > 4000:
            text = text[:4000] + "\n…(截断)"
        blocks.append(f"### {name}\n```json\n{text}\n```")

    if not blocks:
        return None

    from security_agent.agent.health_format import format_tool_outputs_for_user

    formatted = format_tool_outputs_for_user(
        plan.get("intent", "general"),
        tool_trace=[
            {"tool": name, "output": result.get("results", {}).get(name)}
            for name in readonly
        ],
        trace_id=trace_id,
        degraded=True,
        parallel_result=result,
    )
    reply = formatted or (
        f"【工具模式 · 未调用大模型】trace: {trace_id or '—'}\n"
        f"意图: {plan.get('intent', '—')}\n\n"
        + "\n\n".join(blocks)
    )
    return {
        "reply": reply,
        "tool_trace": [
            {
                "degraded": True,
                "tools": readonly,
                "results": result.get("results", {}),
                "errors": result.get("errors", {}),
            }
        ],
        "plan": plan,
        "auto_warn": False,
        "citations": [],
        "token_usage": {},
        "model_used": "tool_fallback",
        "fallback_used": True,
        "degradation_level": DegradationLevel.S2_RULE.value,
        "trace_id": trace_id,
    }


def _format_flow_reply(flow_name: str, result: dict[str, Any]) -> str:
    from security_agent.agent.skill_flow_format import format_skill_flow_reply

    text = format_skill_flow_reply(flow_name, result)
    title = result.get("display_name") or flow_name
    return text.replace(f"【{title}】", f"【{title}·规则兜底】", 1)

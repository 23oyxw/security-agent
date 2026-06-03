"""推断单次 Agent 回复的架构分层（L2/L3），供前端展示."""

from __future__ import annotations

from typing import Any


def infer_execution_meta(result: dict[str, Any]) -> dict[str, Any]:
    """从 brain.chat 结果推断 L2 流程 vs L3 编排."""
    plan = result.get("plan") or {}
    skill_flow = (result.get("skill_flow") or plan.get("skill_flow") or "").strip()
    intent = (plan.get("intent") or "general").strip()
    tool_chain = plan.get("tool_chain") or []

    tools_used: list[str] = []
    l1_tools: list[str] = []
    for t in result.get("tool_trace") or []:
        if not isinstance(t, dict):
            continue
        if t.get("tool"):
            name = str(t["tool"])
            tools_used.append(name)
            l1_tools.append(name)
        elif t.get("skill_flow"):
            tools_used.append(f"flow:{t['skill_flow']}")

    if skill_flow:
        return {
            "layer": "L2",
            "layer_title": "L2 · 确定性流程",
            "route": skill_flow,
            "intent": intent,
            "mode": "skill_flow",
            "tool_count": len(tools_used),
            "hint": "固定步骤剧本（skills/flows），不依赖 LLM 自由选工具",
            "trace_role": "记录本流程各步骤与结果",
            "l1_tools": l1_tools,
        }

    if tool_chain:
        return {
            "layer": "L3",
            "layer_title": "L3 · 编排胶水",
            "route": intent,
            "intent": intent,
            "mode": "tool_chain_llm",
            "tool_count": len(tool_chain),
            "l1_tools": list(tool_chain),
            "hint": "意图识别 → 调用 L1 工具链 → LLM 总结（思考在 L3，执行在 L1）",
            "trace_role": "记录意图、工具链、LLM 阶段",
        }

    if tools_used:
        return {
            "layer": "L3",
            "layer_title": "L3 · 编排胶水",
            "route": intent,
            "intent": intent,
            "mode": "react",
            "tool_count": len(tools_used),
            "l1_tools": l1_tools,
            "hint": "LLM ReAct：多轮推理 → 选择 L1 工具 → 再推理成回复",
            "trace_role": "记录每轮工具调用与推理阶段",
        }

    return {
        "layer": "L3",
        "layer_title": "L3 · 编排胶水",
        "route": intent,
        "intent": intent,
        "mode": "llm_direct",
        "tool_count": 0,
        "l1_tools": [],
        "hint": "主要由 LLM 直接回答（仍属 L3 决策层）",
        "trace_role": "记录对话与模型决策阶段",
    }


def plan_summary(result: dict[str, Any]) -> dict[str, Any]:
    """精简 plan，避免把整个 tool_trace 下发给前端."""
    plan = result.get("plan") or {}
    return {
        "intent": plan.get("intent", ""),
        "skill_flow": plan.get("skill_flow") or result.get("skill_flow") or "",
        "tool_chain": list(plan.get("tool_chain") or [])[:12],
        "hint": (plan.get("hint") or "")[:200],
    }

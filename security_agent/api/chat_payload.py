"""Agent 对话 REST / WebSocket 统一响应构造."""

from __future__ import annotations

from typing import Any

from security_agent.api.execution_meta import infer_execution_meta, plan_summary


def extract_tools_used(tool_trace: list[Any]) -> list[str]:
    names: list[str] = []
    for t in tool_trace:
        if not isinstance(t, dict):
            continue
        if t.get("tool"):
            names.append(str(t["tool"]))
        elif t.get("skill_flow"):
            names.append(f"flow:{t['skill_flow']}")
    return names


def build_chat_payload(result: dict[str, Any], session_id: str) -> dict[str, Any]:
    """从 AgentBrain.chat 结果生成 API/WS 载荷."""
    tool_trace = result.get("tool_trace") or []
    token_usage = result.get("token_usage") or {}
    total = int(token_usage.get("total_tokens") or 0)
    payload: dict[str, Any] = {
        "reply": result.get("reply", result.get("response", "处理完成")),
        "session_id": session_id,
        "tools_used": extract_tools_used(tool_trace),
        "risk_level": "high" if result.get("auto_warn") else "low",
        "cost_tokens": total,
        "token_usage": {
            "prompt_tokens": int(token_usage.get("prompt_tokens") or 0),
            "completion_tokens": int(token_usage.get("completion_tokens") or 0),
            "total_tokens": total,
        },
        "model_used": result.get("model_used") or "",
        "skill_flow": result.get("skill_flow") or "",
        "trace_id": result.get("trace_id") or session_id,
        "degradation_level": result.get("degradation_level", "S0"),
        "fallback_used": bool(result.get("fallback_used")),
        "trace_memo": result.get("trace_memo") or "",
    }
    if result.get("cost_estimate"):
        payload["cost_estimate"] = result["cost_estimate"]
    if result.get("context_usage"):
        payload["context_usage"] = result["context_usage"]
    payload["execution_meta"] = infer_execution_meta(result)
    payload["plan_summary"] = plan_summary(result)
    return payload

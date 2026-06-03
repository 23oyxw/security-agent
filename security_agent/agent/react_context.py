"""ReAct 循环上下文治理 — 工具观测截断、token 压缩、胖消息瘦身."""

from __future__ import annotations

from typing import Any

from security_agent import config


def truncate_observation(text: str, max_chars: int | None = None) -> str:
    """工具观测写入 history 前的硬上限（与 trace 对齐，避免 ReAct 膨胀）."""
    limit = max_chars if max_chars is not None else config.REACT_TOOL_OBSERVATION_MAX_CHARS
    if not text or len(text) <= limit:
        return text
    half = max(limit // 2 - 48, 200)
    return (
        f"{text[:half]}\n"
        f"...[观测已截断，原文 {len(text)} 字，保留首尾共约 {limit} 字]...\n"
        f"{text[-half:]}"
    )


def slim_environment_context(system_ctx: str, max_chars: int | None = None) -> str:
    limit = max_chars if max_chars is not None else config.REACT_PERCEPTION_MAX_CHARS
    if len(system_ctx) <= limit:
        return system_ctx
    return system_ctx[: limit - 32] + "\n...[环境感知已截断]..."


def build_react_user_message(
    user_message: str,
    grounding: str,
    system_ctx: str,
    planner_note: str,
) -> dict[str, str]:
    """ReAct 首轮 user：RAG + 感知 + 意图，均带独立上限."""
    gr = grounding
    if len(gr) > config.REACT_GROUNDING_MAX_CHARS:
        gr = gr[: config.REACT_GROUNDING_MAX_CHARS] + "\n...[知识库 grounding 已截断]..."
    ctx = slim_environment_context(system_ctx)
    note = planner_note[: config.REACT_PLANNER_NOTE_MAX_CHARS]
    content = f"{gr}\n\n[当前系统环境]\n{ctx}\n\n{user_message}\n\n{note}"
    return {"role": "user", "content": content}


def truncate_tool_messages_in_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """遍历 history，压缩 role=tool 的 content."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") != "tool":
            out.append(msg)
            continue
        m = dict(msg)
        content = m.get("content", "")
        if isinstance(content, str):
            m["content"] = truncate_observation(content)
        out.append(m)
    return out


def apply_history_budget(
    messages: list[dict[str, Any]],
    token_manager: Any,
    *,
    max_round_msgs: int | None = None,
) -> list[dict[str, Any]]:
    """ReAct 每轮后：截断 tool 观测 → 条数滑动窗口 → token 压缩."""
    if not messages:
        return messages

    msgs = truncate_tool_messages_in_history(messages)

    max_msgs = (max_round_msgs or config.MAX_HISTORY_ROUNDS) * 4
    if len(msgs) > 1:
        system_parts = [m for m in msgs if m.get("role") == "system"]
        rest = [m for m in msgs if m.get("role") != "system"]
        if len(rest) > max_msgs:
            old = rest[:-max_msgs]
            recent = rest[-max_msgs:]
            user_bits = [m.get("content", "")[:60] for m in old if m.get("role") == "user"]
            summary = (
                "【ReAct 早期轮次摘要】" + "；".join(user_bits[-6:])
                if user_bits
                else "【ReAct 早期轮次已折叠】"
            )
            msgs = (system_parts[:1] or [{"role": "system", "content": ""}]) + [
                {"role": "system", "content": summary},
            ] + recent

    if token_manager.should_compress(msgs):
        msgs = token_manager.compress_messages(msgs)

    return msgs

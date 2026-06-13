"""Tool registry — shared by MCP server, Agent brain, and Streamlit.

重构后: 主干只负责编排与规则校验，具体业务逻辑封装在 Skill 中。
所有工具的实现、描述、参数定义均由 security_agent/skills/*.py 提供。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

from security_agent.audit import log as audit
from security_agent.security.redact import redact_text

ToolFn = Callable[..., Any]

# ---------------------------------------------------------------------------
# Skill 自动发现与注册
# ---------------------------------------------------------------------------

_skill_tools_loaded = False


def _ensure_skills_loaded() -> None:
    """首次调用时自动发现并注册所有 Skill 工具."""
    global _skill_tools_loaded
    if _skill_tools_loaded:
        return
    try:
        from security_agent.skills.registry import auto_discover, merge_skill_tools_into_registry
        auto_discover()
        merge_skill_tools_into_registry()
    except Exception:  # noqa: BLE001
        pass  # Skill 加载失败不影响可用性
    _skill_tools_loaded = True


# ---------------------------------------------------------------------------
# TOOL_REGISTRY — 由 Skill 层自动填充的兼容层
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, tuple[str, dict[str, Any], ToolFn]] = {}


def list_tool_schemas_openai() -> list[dict[str, Any]]:
    """将 TOOL_REGISTRY 转为 OpenAI function calling 格式."""
    _ensure_skills_loaded()
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": meta[0],
                "parameters": meta[1],
            },
        }
        for name, meta in TOOL_REGISTRY.items()
    ]


# 预加载 schema（延迟初始化）
TOOL_SCHEMAS: list[dict[str, Any]] = []


def _lazy_init_schemas() -> None:
    global TOOL_SCHEMAS
    if not TOOL_SCHEMAS:
        TOOL_SCHEMAS = list_tool_schemas_openai()


# ---------------------------------------------------------------------------
# call_tool_local — 统一工具调用入口（编排层）
# ---------------------------------------------------------------------------

async def call_tool_local(
    name: str,
    arguments: dict[str, Any] | None,
    *,
    user_confirmed: bool = False,
) -> str:
    """统一工具调用入口: Skill 注册 -> 规则校验 -> 执行 -> 脱敏."""
    _ensure_skills_loaded()

    if name not in TOOL_REGISTRY:
        # 二次尝试加载（防首次失败）
        _ensure_skills_loaded()
        if name not in TOOL_REGISTRY:
            audit.append_audit("tool_error", {"tool": name, "error": "unknown"}, level="warning")
            return f"未知工具: {name}"

    from security_agent.ops.guardrails import (
        check_mcp_tool_allowed,
        record_tool_failure,
        record_tool_success,
        require_request_budget,
    )

    try:
        require_request_budget("tools")
        check_mcp_tool_allowed(name)
    except Exception as exc:
        audit.append_audit("tool_blocked", {"tool": name, "error": str(exc)}, level="warning")
        return f"工具调用被阻止: {exc}"

    _, _, fn = TOOL_REGISTRY[name]
    args = arguments or {}

    # 规则引擎校验
    from security_agent.rules.engine import RuleVerdict, check_tool

    confirmed = user_confirmed or bool(args.get("confirmed")) or bool(args.get("force"))
    check = check_tool(name, args, user_confirmed=confirmed)
    if check.verdict == RuleVerdict.DENY:
        audit.append_audit("tool_deny", {"tool": name, "reason": check.reason}, level="warning")
        return f"规则拒绝: {check.reason}"
    if check.verdict == RuleVerdict.NEED_CONFIRM:
        audit.append_audit("tool_need_confirm", {"tool": name, "reason": check.reason}, level="info")
        return (
            f"需要用户确认: {check.reason}。"
            "请在智能助手页勾选「确认高危操作」后重试。"
        )

    from security_agent.pipeline.sandbox_gate import sandbox_preview

    sandbox = sandbox_preview(name, args, user_confirmed=confirmed)
    if sandbox.get("verdict") == "deny":
        audit.append_audit("sandbox_deny", {"tool": name, "sandbox": sandbox}, level="warning")
        return f"L2 沙箱拒绝: {sandbox.get('envelope', {}).get('preview', {}).get('message', '预演失败')}"
    if sandbox.get("verdict") == "preview_fail" and sandbox.get("sandbox_required"):
        preview = sandbox.get("envelope", {}).get("preview", {})
        if not preview.get("ok"):
            audit.append_audit("sandbox_preview_fail", {"tool": name, "sandbox": sandbox}, level="warning")
            return f"L2 沙箱预演未通过: {preview.get('message', '命令执行失败')}"

    try:
        result = fn(**args)
        if hasattr(result, "__await__"):
            result = await result
        text = str(result)
        record_tool_success(name)
        return redact_text(text)
    except TypeError as exc:
        record_tool_failure(name, str(exc))
        return f"参数错误: {exc}"
    except Exception as exc:  # noqa: BLE001
        record_tool_failure(name, str(exc))
        audit.append_audit("tool_error", {"tool": name, "error": str(exc)}, level="warning")
        return f"工具执行失败: {exc}"


# ---------------------------------------------------------------------------
# 便捷接口 — 供 UI / 测试使用
# ---------------------------------------------------------------------------

def list_all_tools() -> list[dict[str, Any]]:
    """列出所有已注册工具的摘要（含工具簇）."""
    from security_agent.tools.cluster_map import cluster_for_tool, CLUSTER_LABELS

    _ensure_skills_loaded()
    return [
        {
            "name": name,
            "description": desc,
            "source": "skill",
            "cluster": cluster_for_tool(name),
            "cluster_label": CLUSTER_LABELS.get(cluster_for_tool(name), "通用"),
        }
        for name, (desc, _params, _fn) in TOOL_REGISTRY.items()
    ]
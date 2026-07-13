"""灵活编排：意图识别 → 计划 → 执行 → 归纳."""

from __future__ import annotations

import json
import re
from typing import Any

from security_agent.agent.parallel import (
    PARALLEL_SAFE_TOOLS,
    is_tool_parallel_safe,
    run_security_info_gathering,
    run_tools_parallel,
)

# 意图 → 推荐工具链（可不经 LLM 直接走快捷路径）
INTENT_TOOL_CHAINS: dict[str, list[str]] = {
    "scan": ["query_security_scan_json", "query_security_scan"],
    "full_check": ["run_full_security_check"],
    "processes": ["list_processes", "check_exposed_ports"],
    "report": ["generate_security_report"],
    "monitor_start": ["start_monitor"],
    "monitor_stop": ["stop_monitor"],
    "monitor_status": ["get_monitor_events", "get_system_health"],
    "audit": ["get_audit_log"],
    "health": ["get_system_health"],
    "autonomous": ["run_autonomous_mission"],
    "terminal": ["run_terminal_command"],
    "scan_report": [],  # L2 flow，见 INTENT_SKILL_FLOWS
    "alert_response": [],
    "secure_exec_flow": [],
    "block": [],  # L2 block_process
}

# 意图 → L2 Skill Flow（主干只拼接，逻辑在 skills/flows）
INTENT_SKILL_FLOWS: dict[str, str] = {
    "scan_report": "scan_report",
    "alert_response": "alert_response",
    "secure_exec_flow": "secure_exec",
    "block": "block_process",
}

INTENT_TOOL_CHAINS["parallel_info"] = [
    "query_security_scan_json",
    "list_processes",
    "get_system_health",
    "check_exposed_ports",
]


def detect_intent(text: str) -> str:
    t = text.lower().strip()
    # L2 Skill Flow 关键词优先（避免「扫描」误匹配到单工具 scan）
    if any(k in t for k in ("扫描报告", "一键扫描报告", "生成扫描报告", "扫描并报告")):
        return "scan_report"
    if any(k in t for k in ("告警响应", "处理告警", "响应告警", "告警处置")):
        return "alert_response"
    if any(k in t for k in ("安全执行", "三层防御执行", "经安全闸门执行")):
        return "secure_exec_flow"
    if re.search(r"拦截|kill|终止|block", t) and re.search(r"\d{2,}", t):
        return "block"
    if any(k in t for k in ("综合体检", "全面检查", "一键体检", "full check")):
        return "full_check"
    if any(k in t for k in ("并行采集", "并行扫描", "同时扫描", "快速体检", "快速检查")):
        return "parallel_info"
    if any(k in t for k in ("扫描", "风险", "安全检查", "漏洞")):
        return "scan"
    if any(k in t for k in ("异常进程", "检查进程", "进程检查", "可疑进程", "高危进程", "进程列表", "列出进程", "list process")):
        return "processes"
    if any(k in t for k in ("报告", "html", "报表")):
        return "report"
    if any(k in t for k in ("停止监控", "关闭监控")):
        return "monitor_stop"
    if any(k in t for k in ("启动监控", "开始监控", "开监控")):
        return "monitor_start"
    if any(k in t for k in ("监控事件", "监控状态", "监控")):
        return "monitor_status"
    if any(k in t for k in ("审计", "日志")):
        return "audit"
    if any(k in t for k in ("cpu", "内存", "健康", "系统状态")):
        return "health"
    if any(k in t for k in ("自主", "自动执行", "一键", "mission", "工作流")):
        return "autonomous"
    if any(k in t for k in ("终端", "执行命令", "shell", "ps aux")):
        return "terminal"
    return "general"


_DEFAULT_AUTONOMOUS_GOAL = (
    "全量安全巡检：检查开放端口、高危进程、系统健康与敏感路径，并输出执行摘要"
)

_AUTONOMOUS_TRIGGERS = (
    "执行自主运维任务",
    "自主运维",
    "运行自主任务",
    "执行自主任务",
    "一键自主运维",
)


def resolve_autonomous_goal(user_message: str) -> str:
    """从用户话术解析自主任务 goal；泛化点击用语时使用默认巡检目标."""
    msg = (user_message or "").strip()
    if not msg:
        return _DEFAULT_AUTONOMOUS_GOAL
    for trigger in _AUTONOMOUS_TRIGGERS:
        if msg == trigger:
            return _DEFAULT_AUTONOMOUS_GOAL
        for sep in ("：", ":", "—", "-"):
            prefix = f"{trigger}{sep}"
            if msg.startswith(prefix):
                tail = msg[len(prefix) :].strip()
                return tail or _DEFAULT_AUTONOMOUS_GOAL
    low = msg.lower()
    if any(k in msg for k in ("进程", "process", "可疑进程")):
        return f"高危进程排查与风险评估：{msg}"
    if any(k in msg for k in ("日志", "审计", "登录失败")):
        return f"日志异常审计：{msg}"
    if any(k in msg for k in ("漏洞", "加固", "ssh", "防火墙")):
        return f"环境安全配置检查：{msg}"
    if any(k in msg for k in ("扫描", "端口", "暴露")):
        return f"全量安全扫描：{msg}"
    if len(msg) <= 12 and any(k in msg for k in ("自主", "运维", "mission")):
        return _DEFAULT_AUTONOMOUS_GOAL
    return msg


def build_tool_args(tool_name: str, user_message: str) -> dict[str, Any]:
    """为编排工具链构造参数（避免空 args 导致 TypeError）."""
    if tool_name == "run_autonomous_mission":
        return {"goal": resolve_autonomous_goal(user_message)}
    if tool_name == "list_processes":
        return {"limit": 50}
    return {}


def expand_health_tool_chain(message: str, chain: list[str] | None = None) -> list[str]:
    """按用户话术扩展健康类工具链（CPU/内存/磁盘/进程/端口）."""
    t = (message or "").lower()
    out: list[str] = list(chain or ["get_system_health"])
    if "get_system_health" not in out:
        out.insert(0, "get_system_health")
    if any(k in t for k in ("进程", "process", "可疑")) and "list_processes" not in out:
        out.append("list_processes")
    if any(k in t for k in ("端口", "port", "暴露", "监听")) and "check_exposed_ports" not in out:
        out.append("check_exposed_ports")
    if any(k in t for k in ("扫描", "风险", "安全", "汇总")) and "query_security_scan_json" not in out:
        if any(k in t for k in ("进程", "端口", "汇总", "指标")):
            pass  # 健康汇总不强制全扫
    # 「汇总…指标」类话术默认带上进程与端口
    if any(k in t for k in ("汇总", "关键指标", "全面", "体检")):
        for name in ("list_processes", "check_exposed_ports"):
            if name not in out:
                out.append(name)
    return out


def build_plan(
    user_message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from security_agent.agent.follow_up import resolve_follow_up

    msg = user_message
    intent = detect_intent(user_message)
    follow = resolve_follow_up(user_message, history)
    if follow:
        intent = follow["intent"]
        msg = follow.get("enriched_message") or user_message
    skill_flow = INTENT_SKILL_FLOWS.get(intent)
    if follow and follow.get("skill_flow"):
        skill_flow = follow["skill_flow"]
    chain = [] if skill_flow else INTENT_TOOL_CHAINS.get(intent, [])
    if intent == "health":
        chain = expand_health_tool_chain(user_message, chain)
    tool_args: dict[str, dict[str, Any]] = {}
    for name in chain:
        args = build_tool_args(name, msg)
        if args:
            tool_args[name] = args
    hint = _plan_hint(intent)
    if follow and follow.get("hint"):
        hint = follow["hint"]
    return {
        "intent": intent,
        "tool_chain": chain,
        "tool_args": tool_args,
        "skill_flow": skill_flow,
        "use_llm_tools": intent == "general",
        "hint": hint,
        "user_message_resolved": msg,
        "follow_up": bool(follow),
    }


def build_skill_flow_context(flow_name: str, user_message: str) -> dict[str, Any]:
    """为 L2 flow 从用户话术中抽取上下文."""
    ctx: dict[str, Any] = {"user_message": user_message}
    if flow_name == "secure_exec":
        cmd = _extract_shell_command(user_message)
        if cmd:
            ctx["command"] = cmd
            ctx["user_confirmed"] = any(k in user_message for k in ("已确认", "确认执行", "我确认"))
    elif flow_name == "alert_response":
        ctx["alert_event"] = {"message": user_message, "source": "chat"}
    elif flow_name == "block_process":
        m = re.search(r"\b(\d{2,6})\b", user_message)
        if m:
            ctx["pid"] = int(m.group(1))
        ctx["force"] = any(k in user_message for k in ("强制", "force", "已确认"))
    return ctx


def _extract_shell_command(text: str) -> str:
    m = re.search(r"`([^`]+)`", text)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"(?:安全执行|三层防御执行|经安全闸门执行)\s*[:：]?\s*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()[:500]
    for prefix in ("执行命令：", "执行命令:", "执行命令 ", "执行：", "执行:", "运行 "):
        if prefix in text:
            return text.split(prefix, 1)[-1].strip()[:500]
    return ""


def _plan_hint(intent: str) -> str:
    hints = {
        "scan": "先 JSON 扫描再输出人读摘要",
        "full_check": "运行综合体检并总结关键项",
        "parallel_info": "并行执行多个只读扫描（安全、进程、健康、端口），提速响应",
        "processes": "列出进程并检查端口暴露，用表格总结异常项（勿重复调用加固/日志等无关工具）",
        "report": "扫描后生成 HTML 报告（默认使用 Budget 模型生成 AI 摘要）",
        "monitor_start": "启动监控并说明如何查看事件",
        "monitor_stop": "停止监控",
        "monitor_status": "读取监控事件与系统健康",
        "block": "先 list/scan 确认 PID 再 block，需用户确认",
        "autonomous": "调用 run_autonomous_mission(goal=用户目标)；仅说「执行自主运维任务」时已自动填入全量安全巡检目标",
        "scan_report": "L2 流程：扫描+端口+健康 → 文本/HTML 报告",
        "alert_response": "L2 流程：告警路由到各 Skill on_alert",
        "secure_exec_flow": "L2 流程：三层防御评估 → 安全执行；请在消息中用反引号标出命令",
        "block": "L2 流程：进程拦截(kill)；消息中需含 PID，高危外需「强制」",
        "general": "根据问题自主选择工具，可多步组合",
    }
    return hints.get(intent, "")


def format_plan_for_llm(plan: dict[str, Any]) -> str:
    if not plan.get("tool_chain"):
        return f"[编排] 意图={plan['intent']}；{plan['hint']}；请自选合适工具。"
    tools = " → ".join(plan["tool_chain"])
    return f"[编排] 意图={plan['intent']}；建议工具链: {tools}；{plan['hint']}"


# ============================================================
# 三层防御集成（来自 qt01 赛题版，适配主项目 Streamlit/FastAPI）
# ============================================================


def get_three_layer_defense():
    """懒加载三层防御引擎."""
    try:
        from security_agent.safety_gate.three_layer_defense import ThreeLayerDefenseEngine

        return ThreeLayerDefenseEngine()
    except Exception:
        return None


def _normalize_defense_result(defense_result: Any) -> dict[str, Any]:
    """将三层防御结果统一为编排器兼容格式."""
    if isinstance(defense_result, dict):
        data = defense_result
    elif hasattr(defense_result, "to_dict"):
        data = defense_result.to_dict()
    else:
        data = {"raw": str(defense_result)}

    verdict = str(data.get("overall_verdict") or data.get("verdict") or "").lower()
    blocked = verdict in ("deny", "escalate", "quarantine")
    return {
        **data,
        "allowed": not blocked,
        "blocked_by_layer": "three_layer_defense" if blocked else "",
        "block_reason": data.get("message", "安全策略拒绝执行"),
        "requires_confirmation": bool(data.get("requires_user_confirmation")),
        "requires_approval": bool(data.get("requires_human_approval")),
    }


async def run_with_three_layer_defense(
    command: str,
    *,
    user_message: str = "",
    user_role: str = "operator",
    sudo: bool = False,
    user_confirmed: bool = False,
    trace_id: str = "",
) -> dict[str, Any]:
    """经三层防御评估后执行终端命令 — 主项目统一安全执行入口.

    流程: L1静态30% → L2意图35% → L3受限35% → 沙箱/PrivilegeBroker 执行
    """
    from security_agent.audit.reasoning_trace import ReasoningTrace, TraceStatus
    from security_agent.terminal.executor import run_terminal

    engine = get_three_layer_defense()
    if not engine:
        return {"allowed": False, "trace_id": trace_id, "reason": "三层防御引擎不可用"}

    trace = ReasoningTrace(user_message or command, strategy="three_layer")
    if trace_id:
        trace.trace_id = trace_id

    with trace:
        trace.update_status(TraceStatus.SAFETY_CHECK)
        defense_result = await engine.evaluate(
            command,
            target_type="terminal",
            user_message=user_message or command,
            trace_id=trace.trace_id,
            user=user_role,
            sudo=sudo,
        )
        normalized = _normalize_defense_result(defense_result)
        trace.record_safety_check(
            target=command[:200],
            target_type="terminal",
            layer_scores={layer.get("layer", ""): layer for layer in normalized.get("layers", [])},
            overall_verdict=str(normalized.get("overall_verdict", "")),
            overall_score=float(normalized.get("overall_score", 0)),
            decision_path=normalized.get("decision_path", []),
            requires_confirmation=bool(normalized.get("requires_confirmation")),
            requires_approval=bool(normalized.get("requires_approval")),
            blocked=not normalized.get("allowed", True),
            block_reason=normalized.get("block_reason", ""),
        )

        if not normalized.get("allowed", True):
            trace.update_status(TraceStatus.FAILED)
            return {
                "allowed": False,
                "defense_result": normalized,
                "execution_result": None,
                "trace_id": trace.trace_id,
                "blocked_by": normalized.get("blocked_by_layer", "three_layer_defense"),
                "reason": normalized.get("block_reason", "安全策略拒绝执行"),
            }

        if normalized.get("requires_confirmation") and not user_confirmed:
            trace.update_status(TraceStatus.INTERRUPTED)
            return {
                "allowed": False,
                "defense_result": normalized,
                "execution_result": None,
                "trace_id": trace.trace_id,
                "reason": "操作需用户确认后执行",
                "requires_confirmation": True,
            }

        trace.update_status(TraceStatus.EXECUTING)
        exec_result = await run_terminal(
            command,
            user_confirmed=user_confirmed or not normalized.get("requires_confirmation"),
        )
        trace.record_action(
            tool_name="terminal_exec",
            tool_id="run_terminal_command",
            arguments={"command": command[:200]},
            result_summary=exec_result.to_text()[:500],
            success=exec_result.ok,
        )
        trace.update_status(TraceStatus.COMPLETED if exec_result.ok else TraceStatus.FAILED)

        return {
            "allowed": True,
            "defense_result": normalized,
            "execution_result": {
                "ok": exec_result.ok,
                "exit_code": exec_result.exit_code,
                "stdout": exec_result.stdout[:2000],
                "stderr": exec_result.stderr[:1000],
                "executed_as_user": exec_result.executed_as_user,
            },
            "trace_id": trace.trace_id,
        }

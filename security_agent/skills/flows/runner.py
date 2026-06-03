"""L2 Skill Flow 执行器 — 编排 L1 工具完成多步运维流程."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from security_agent.audit import log as audit
from security_agent.timeutil import now_iso

FlowStep = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class FlowDef:
    name: str
    display_name: str
    description: str
    steps: list[FlowStep] = field(default_factory=list)


async def _step_safety_evaluate(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 三层防御评估."""
    from security_agent.agent.orchestrator import get_three_layer_defense

    command = ctx.get("command", "")
    engine = get_three_layer_defense()
    if not engine:
        return {"ok": False, "error": "三层防御引擎不可用"}
    result = await engine.evaluate(
        command,
        target_type="terminal",
        user_message=ctx.get("user_message", command),
        trace_id=ctx.get("trace_id", ""),
    )
    data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    ctx["defense"] = data
    verdict = str(data.get("overall_verdict", "")).lower()
    ctx["blocked"] = verdict in ("deny", "escalate", "quarantine")
    return {"ok": not ctx["blocked"], "defense": data}


async def _step_terminal_exec(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 经 orchestrator 安全执行."""
    from security_agent.agent.orchestrator import run_with_three_layer_defense

    command = ctx.get("command", "")
    result = await run_with_three_layer_defense(
        command,
        user_message=ctx.get("user_message", command),
        user_confirmed=bool(ctx.get("user_confirmed")),
        trace_id=ctx.get("trace_id", ""),
    )
    ctx["execution"] = result
    return {"ok": bool(result.get("allowed")), "result": result}


async def _step_route_alert(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 告警路由到 Skill on_alert."""
    from security_agent.skills.registry import route_alert_to_skills

    event = ctx.get("alert_event") or ctx.get("event") or {}
    results = await route_alert_to_skills(event)
    ctx["alert_responses"] = results
    return {"ok": True, "responses": results}


async def _step_security_scan(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 进程 + 敏感路径扫描."""
    from security_agent.scanner.engine import run_security_scan

    data = run_security_scan()
    ctx["scan"] = data
    return {
        "ok": True,
        "step": "security_scan",
        "risk_count": data.get("risk_count", 0),
    }


async def _step_exposed_ports(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 高危端口暴露检测，合并进 scan.risks."""
    from security_agent.tools.system_info import check_exposed_ports

    exposed = check_exposed_ports()
    ctx["exposed_ports"] = exposed
    scan = dict(ctx.get("scan") or {})
    alerts = exposed.get("alerts") or []
    if alerts:
        merged = list(scan.get("risks", []))
        seen = {json.dumps(r, sort_keys=True, default=str) for r in merged}
        for a in alerts:
            key = json.dumps(a, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                merged.append(a)
        scan["risks"] = merged
        scan["risk_count"] = len(merged)
    scan["exposed_ports"] = exposed
    ctx["scan"] = scan
    return {
        "ok": True,
        "step": "exposed_ports",
        "risky_count": exposed.get("risky_count", 0),
        "ports_ok": exposed.get("ok", True),
        "message": exposed.get("message", ""),
    }


async def _step_system_health(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 采集 CPU/内存等健康指标写入 scan 上下文."""
    from security_agent.tools.system_info import get_system_health

    health = get_system_health()
    ctx["health"] = health
    scan = dict(ctx.get("scan") or {})
    scan["health"] = health
    ctx["scan"] = scan
    return {"ok": True, "step": "system_health"}


async def _step_generate_report(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 生成可读文本报告."""
    from security_agent.scanner.engine import format_security_report

    scan = ctx.get("scan") or {}
    report = format_security_report(scan)
    ctx["report"] = report[:8000]
    return {"ok": True, "step": "text_report", "report_len": len(report)}


async def _step_generate_html(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 生成 HTML 报告文件."""
    from security_agent.scanner.engine import generate_html_report

    scan = ctx.get("scan") or {}
    path = generate_html_report(scan)
    ctx["report_html_path"] = path
    return {"ok": True, "step": "html_report", "path": path}


async def _step_block_process(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 终止指定 PID（高危校验或强制）."""
    import re

    from security_agent.scanner.engine import block_process

    pid = ctx.get("pid")
    if pid is None:
        msg = ctx.get("user_message", "")
        m = re.search(r"\b(\d{2,6})\b", msg)
        if m:
            pid = int(m.group(1))
    if not pid:
        return {"ok": False, "step": "block_process", "error": "未提供 PID（表单或消息中的数字）"}
    pid = int(pid)
    force = bool(ctx.get("force"))
    result = block_process(pid, force=force)
    ctx["execution"] = result
    return {"ok": bool(result.get("ok")), "step": "block_process", **result}


async def _step_cleanup_scan(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 扫描可清理项."""
    from security_agent.skills.system_cleanup_skill import SystemCleanupSkill

    skill = SystemCleanupSkill()
    result = skill.scan_all()
    ctx["cleanup_scan"] = result
    return {"ok": True, "step": "cleanup_scan", "total": result["total_human"], "recommendation": result["recommendation"]}


async def _step_cleanup_run(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 执行清理（仅安全类）。"""
    from security_agent.skills.system_cleanup_skill import SystemCleanupSkill

    skill = SystemCleanupSkill()
    confirm_all = bool(ctx.get("confirm_all"))
    categories = ctx.get("categories")
    result = skill.execute(categories, confirm_all=confirm_all)
    ctx["cleanup_result"] = result
    if result.get("blocked"):
        return {"ok": False, "step": "cleanup_run", "blocked": True, "message": result.get("message")}
    return {"ok": True, "step": "cleanup_run", "executed": result.get("executed", 0), "succeeded": result.get("succeeded", 0)}


async def _step_cpu_stress(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: CPU 多核压测 + 阈值监控（后台执行，返回启动信息）。"""
    from security_agent.skills.cpu_tuning_skill import start_cpu_stress

    mode = str(ctx.get("mode", "multi"))
    duration = int(ctx.get("duration", 60))
    threshold = float(ctx.get("threshold", 85.0))
    result = start_cpu_stress(mode=mode, duration=duration, threshold=threshold)
    ctx["cpu_stress"] = result
    return {"ok": result.get("ok", False), "step": "cpu_stress", **result}


async def _step_cpu_stop(ctx: dict[str, Any]) -> dict[str, Any]:
    """L1: 停止 CPU 压测."""
    from security_agent.skills.cpu_tuning_skill import stop_cpu_stress

    result = stop_cpu_stress()
    ctx["cpu_stop"] = result
    return {"ok": True, "step": "cpu_stop", **result}


# L2 flow 定义（步骤链，不含 LLM 编排）
_FLOWS: dict[str, FlowDef] = {
    "secure_exec": FlowDef(
        name="secure_exec",
        display_name="安全命令执行",
        description="三层防御评估 → 确认 → 沙箱/降权执行",
        steps=[_step_safety_evaluate, _step_terminal_exec],
    ),
    "alert_response": FlowDef(
        name="alert_response",
        display_name="告警响应",
        description="告警事件 → Skill 路由 → 汇总处置建议",
        steps=[_step_route_alert],
    ),
    "scan_report": FlowDef(
        name="scan_report",
        display_name="扫描报告",
        description="进程/路径扫描 → 端口暴露 → 健康摘要 → 文本+HTML 报告",
        steps=[
            _step_security_scan,
            _step_exposed_ports,
            _step_system_health,
            _step_generate_report,
            _step_generate_html,
        ],
    ),
    "block_process": FlowDef(
        name="block_process",
        display_name="进程拦截 (kill)",
        description="解析 PID → 高危校验 → terminate/kill",
        steps=[_step_block_process],
    ),
    "system_cleanup": FlowDef(
        name="system_cleanup",
        display_name="系统垃圾清理",
        description="扫描可清理项 → 分类报告 → 安全执行（APT/Journal/tmp/pip/Docker/内核/回收站/日志）",
        steps=[_step_cleanup_scan, _step_cleanup_run],
    ),
    "cpu_stress": FlowDef(
        name="cpu_stress",
        display_name="CPU 多核压测",
        description="多核压测 → 阈值监控自动停止 / 一键手动停止",
        steps=[_step_cpu_stress, _step_cpu_stop],
    ),
}


def list_flows() -> list[dict[str, str]]:
    """列出可用 L2 flow."""
    out: list[dict[str, str]] = []
    for f in _FLOWS.values():
        labels = []
        for step_fn in f.steps:
            name = step_fn.__name__.replace("_step_", "")
            labels.append(name)
        out.append(
            {
                "name": f.name,
                "display_name": f.display_name,
                "description": f.description,
                "step_count": str(len(f.steps)),
                "steps": labels,
            }
        )
    return out


async def run_skill_flow(
    flow_name: str,
    context: dict[str, Any] | None = None,
    *,
    trace_id: str = "",
) -> dict[str, Any]:
    """执行命名 L2 Skill Flow（L3 orchestrator 的胶水入口）.

    Args:
        flow_name: secure_exec | alert_response | scan_report
        context: 流程上下文（command / alert_event / user_message 等）
        trace_id: 可选链路 ID

    Returns:
        { flow, trace_id, ok, steps, context }
    """
    flow = _FLOWS.get(flow_name)
    if not flow:
        return {
            "ok": False,
            "error": f"未知 flow: {flow_name}",
            "available": [f.name for f in _FLOWS.values()],
        }

    ctx = dict(context or {})
    tid = (trace_id or ctx.get("trace_id") or "").strip()
    if not tid:
        tid = f"trace-{uuid.uuid4().hex[:12]}"
    elif not tid.startswith("trace-"):
        tid = f"trace-{tid[:12]}"
    ctx["trace_id"] = tid
    ctx.setdefault("started_at", now_iso())
    alert_ev = ctx.get("alert_event") or ctx.get("event")
    if isinstance(alert_ev, dict) and alert_ev and not alert_ev.get("ts"):
        alert_ev = {**alert_ev, "ts": now_iso()}
        ctx["alert_event"] = alert_ev
    step_results: list[dict[str, Any]] = []

    audit.append_audit(
        "skill_flow_start",
        {"flow": flow_name, "trace_id": tid, "context_keys": list(ctx.keys())},
    )

    import time

    ok = True
    for i, step in enumerate(flow.steps):
        try:
            t0 = time.perf_counter()
            out = await step(ctx)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            step_results.append({"index": i, "duration_ms": elapsed_ms, **out})
            if not out.get("ok", True):
                ok = False
                if ctx.get("blocked"):
                    break
                break
        except Exception as exc:  # noqa: BLE001
            step_results.append({"index": i, "ok": False, "error": str(exc)})
            ok = False
            break

    result = {
        "flow": flow_name,
        "display_name": flow.display_name,
        "trace_id": tid,
        "ok": ok,
        "steps": step_results,
        "started_at": ctx.get("started_at") or now_iso(),
        "finished_at": now_iso(),
    }
    if ctx.get("alert_event"):
        result["alert_event"] = ctx["alert_event"]
    for key in (
        "command",
        "report",
        "report_html_path",
        "execution",
        "defense",
        "scan",
        "exposed_ports",
        "health",
        "alert_responses",
    ):
        if key in ctx:
            result[key] = ctx[key]
    audit.append_audit("skill_flow_end", result)
    return result

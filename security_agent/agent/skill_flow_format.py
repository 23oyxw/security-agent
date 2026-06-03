"""L2 Skill Flow 回复格式化 — 面向运维人员可读，避免 JSON 卷宗."""

from __future__ import annotations

from typing import Any


def _layer_label(layer: str) -> str:
    mapping = {
        "static_risk": "L1 静态风险",
        "dynamic_intent": "L2 意图审计",
        "restricted_exec": "L3 受限执行",
    }
    return mapping.get(layer, layer or "—")


def _unpack_secure_exec(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    """返回 (defense, execution_result, command)."""
    defense = dict(result.get("defense") or {})
    wrap = result.get("execution") or {}
    if not defense and isinstance(wrap.get("defense_result"), dict):
        defense = wrap["defense_result"]
    exec_res = wrap.get("execution_result") if isinstance(wrap.get("execution_result"), dict) else {}
    if not exec_res and wrap.get("stdout") is not None:
        exec_res = wrap
    cmd = (
        result.get("command")
        or defense.get("target")
        or wrap.get("target")
        or ""
    )
    return defense, exec_res, str(cmd).strip()


def format_secure_exec_reply(result: dict[str, Any]) -> str:
    title = result.get("display_name") or "安全命令执行"
    tid = result.get("trace_id", "")
    defense, exec_res, command = _unpack_secure_exec(result)

    if not result.get("ok"):
        reason = defense.get("block_reason") or defense.get("message") or "未通过安全评估"
        lines = [
            f"【{title}】未执行",
            f"命令: `{command or '—'}`",
            f"原因: {reason}",
            f"Trace: {tid}",
        ]
        return "\n".join(lines)

    verdict = str(defense.get("overall_verdict", "—"))
    score = defense.get("overall_score")
    score_s = f"{float(score):.1f}" if score is not None else "—"
    msg = defense.get("message") or defense.get("block_reason") or ""

    lines = [
        f"【{title}】{verdict} · 总分 {score_s}",
        f"命令: `{command or '—'}`",
    ]
    if msg:
        lines.append(f"说明: {msg}")

    layers = defense.get("layers") or []
    if layers:
        lines.append("")
        lines.append("三层防御:")
        for layer in layers:
            name = _layer_label(str(layer.get("layer", "")))
            v = layer.get("verdict", "—")
            sc = layer.get("score")
            sc_s = f"{float(sc):.0f}" if sc is not None else "—"
            detail = (layer.get("detail") or "")[:120]
            lines.append(f"  · {name} · {v} {sc_s} — {detail}")

    ok = exec_res.get("ok", True)
    code = exec_res.get("exit_code")
    stdout = (exec_res.get("stdout") or "").strip()
    stderr = (exec_res.get("stderr") or "").strip()

    lines.append("")
    lines.append(f"执行结果: {'成功' if ok else '失败'} · 退出码 {code if code is not None else '—'}")
    if stdout:
        cap = 1800
        body = stdout if len(stdout) <= cap else stdout[:cap] + f"\n…（输出已截断，共约 {len(stdout)} 字符，完整见 Trace）"
        lines.append("──────── 标准输出 ────────")
        lines.append(body)
        lines.append("────────────────────────")
    elif ok:
        lines.append("（无标准输出）")
    if stderr:
        lines.append(f"标准错误: {stderr[:500]}")

    lines.append(f"\nTrace: {tid}")
    return "\n".join(lines)


def format_alert_response_reply(result: dict[str, Any]) -> str:
    title = result.get("display_name") or "告警响应"
    tid = result.get("trace_id", "")
    responses = result.get("alert_responses") or []
    lines = [f"【{title}】完成", f"已路由 {len(responses)} 个 Skill:"]
    for i, r in enumerate(responses[:12], 1):
        if isinstance(r, dict):
            skill = r.get("skill") or r.get("name") or "skill"
            summary = (r.get("summary") or r.get("message") or r.get("status") or "")[:200]
            plan = r.get("plan_summary") if isinstance(r.get("plan_summary"), dict) else {}
            rc = plan.get("root_cause") or r.get("root_cause")
            if rc:
                summary = f"根因: {rc}" + (f"；{summary}" if summary else "")
            elif r.get("recommendation"):
                summary = str(r["recommendation"])[:200]
            lines.append(f"  {i}. {skill}: {summary or '—'}")
        else:
            lines.append(f"  {i}. {str(r)[:200]}")
    if len(responses) > 12:
        lines.append(f"  … 另有 {len(responses) - 12} 条")
    lines.append(f"\nTrace: {tid}")
    return "\n".join(lines)


def format_skill_flow_reply(flow_name: str, result: dict[str, Any]) -> str:
    """统一 L2 流程人读回复."""
    title = result.get("display_name") or flow_name
    tid = result.get("trace_id", "")
    if not result.get("ok"):
        err = ""
        for st in result.get("steps") or []:
            if st.get("error"):
                err = str(st["error"])[:300]
                break
        return (
            f"【{title}】未完全成功\n"
            f"{err or '请查看 Skill 流程页步骤或 Trace'}\n"
            f"Trace: {tid}"
        )

    if flow_name == "secure_exec":
        return format_secure_exec_reply(result)
    if flow_name == "scan_report":
        report = (result.get("report") or "")[:3500]
        scan = result.get("scan") or {}
        risks = scan.get("risk_count", len(scan.get("risks", [])))
        html_path = result.get("report_html_path", "")
        extra = f"\nHTML 报告: {html_path}" if html_path else ""
        return (
            f"【{title}】完成\n"
            f"风险项: {risks}{extra}\n\n"
            f"{report or '（无报告正文）'}\n\n"
            f"Trace: {tid}"
        )
    if flow_name == "block_process":
        ex = result.get("execution") or {}
        msg = ex.get("message") or ex.get("reason") or ""
        if not msg and isinstance(ex.get("result"), dict):
            msg = ex["result"].get("message", "")
        return f"【{title}】{'成功' if result.get('ok') else '未成功'}\n{msg or '—'}\n\nTrace: {tid}"
    if flow_name == "alert_response":
        return format_alert_response_reply(result)
    return f"【{title}】完成\nTrace: {tid}"

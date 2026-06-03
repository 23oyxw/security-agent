"""Trace 导出：TXT = 执行纪要；HTML = Python 绘图可视化分析."""

from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any

from security_agent.audit.trace_report_charts import build_visual_sections, build_viz_strategy_html

_STAGE_LABELS: dict[str, str] = {
    "receive_request": "接收用户请求",
    "skill_flow_start": "开始 L2 固定流程",
    "skill_flow_end": "完成 L2 固定流程",
    "post_verify": "执行结果校验",
    "environment_probe": "环境探测 / 工具链",
    "environment_probe_result": "工具链结果汇总",
    "inference_decision": "LLM 推理决策",
    "safety_check": "安全校验",
    "execution": "命令或工具执行",
    "degradation": "服务降级",
}

_FLOW_DISPLAY: dict[str, str] = {
    "secure_exec": "安全命令执行",
    "scan_report": "扫描报告",
    "alert_response": "告警响应",
    "block_process": "进程拦截",
}

_FLOW_STEP_CN: dict[str, str] = {
    "security_scan": "进程/路径扫描",
    "exposed_ports": "端口暴露检测",
    "system_health": "系统健康",
    "text_report": "文本报告",
    "html_report": "HTML 报告",
    "safety_evaluate": "三层防御评估",
    "terminal_exec": "安全执行",
    "route_alert": "告警路由",
    "block_process": "进程拦截",
}


def _stage_duration_deltas(stages: list[dict[str, Any]]) -> list[int]:
    """将 SQLite 中可能为「累计耗时」的 duration_ms 转为单阶段增量."""
    raw = [int(s.get("duration_ms") or 0) for s in stages]
    if not raw:
        return []
    if len(raw) == 1:
        return raw
    monotonic = all(raw[i] <= raw[i + 1] for i in range(len(raw) - 1))
    if monotonic and raw[-1] > raw[0] * 1.2:
        deltas = [raw[0]]
        for i in range(1, len(raw)):
            deltas.append(max(0, raw[i] - raw[i - 1]))
        return deltas
    return raw


def _parse_jsonish(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return val
    return val


def _ingest_skill_flow_payload(facts: dict[str, Any], payload: dict[str, Any]) -> None:
    """从 skill_flow_end 卷宗合并 L2 业务结果."""
    if not payload:
        return
    facts["flow"] = payload.get("flow") or facts["flow"]
    facts["flow_ok"] = payload.get("ok", facts["flow_ok"])
    if facts["flow"]:
        facts["route"] = f"L2 · {_FLOW_DISPLAY.get(facts['flow'], facts['flow'])}"

    steps = payload.get("steps") or payload.get("flow_steps") or []
    if steps:
        facts["flow_steps"] = steps

    scan = payload.get("scan") or {}
    if scan:
        facts["risk_count"] = scan.get("risk_count", 0)
        risks = scan.get("risks") or []
        from security_agent.audit.trace_chart_metrics import normalize_risk_level

        by_level: dict[str, int] = {}
        for r in risks:
            lv = normalize_risk_level(r.get("level"))
            by_level[lv] = by_level.get(lv, 0) + 1
        facts["risk_by_level"] = by_level
        exp = scan.get("exposed_ports") or payload.get("exposed_ports") or {}
        if isinstance(exp, dict):
            facts["risky_ports"] = exp.get("risky_count", facts["risky_ports"])

    if payload.get("risk_count") is not None:
        facts["risk_count"] = payload["risk_count"]
    if payload.get("risky_ports") is not None:
        facts["risky_ports"] = payload["risky_ports"]
    if payload.get("report_len") is not None:
        facts["report_len"] = payload["report_len"]
    if payload.get("report_html_path"):
        facts["report_html_path"] = payload["report_html_path"]
    if payload.get("report") and facts["report_len"] is None:
        facts["report_len"] = len(str(payload["report"]))
    report = (payload.get("report") or "").strip()
    if report:
        facts["report_excerpt"] = report[:2500]

    health = payload.get("health") or scan.get("health") or {}
    if isinstance(health, dict) and health:
        facts["health"] = health

    if payload.get("alert_responses"):
        facts["alert_responses"] = payload["alert_responses"]
    alert_ev = payload.get("alert_event") or {}
    if isinstance(alert_ev, dict) and alert_ev:
        facts["alert_event"] = alert_ev

    risks = (scan.get("risks") or []) if scan else []
    if risks:
        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        for r in risks:
            if not isinstance(r, dict):
                continue
            key = f"{r.get('port')}|{r.get('pid')}|{(r.get('message') or '')[:60]}"
            if key in seen:
                continue
            seen.add(key)
            items.append(r)
        facts["risk_items"] = items

    exp = scan.get("exposed_ports") or payload.get("exposed_ports") or {}
    if isinstance(exp, dict):
        facts["listen_count"] = exp.get("listener_count", facts.get("listen_count"))
        if facts.get("risky_ports") is None:
            facts["risky_ports"] = exp.get("risky_count")
        risky = [ln for ln in (exp.get("listeners") or []) if isinstance(ln, dict) and ln.get("risky")]
        if risky:
            facts["risky_listeners"] = risky[:12]


def _level_badge(level: str) -> str:
    lv = str(level or "—")
    cls = "risk-low"
    if lv in ("高", "高危") or lv.lower() in ("high", "critical"):
        cls = "risk-high"
    elif lv in ("中", "medium") or lv.lower() == "medium":
        cls = "risk-med"
    return f'<span class="badge-lv {cls}">{html_lib.escape(lv)}</span>'


def _findings_wrap(title: str, parts: list[str]) -> str:
    if not parts:
        return ""
    return (
        f'<section class="panel findings-panel"><h2 style="margin:0 0 12px;font-size:16px;">'
        f"{html_lib.escape(title)}</h2>{''.join(parts)}</section>"
    )


def _findings_secure_exec_parts(f: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    cmd = f.get("command") or ""
    if cmd:
        parts.append(f'<p class="finding-lead"><b>执行命令：</b><code>{html_lib.escape(cmd)}</code></p>')
    if f.get("verdict") or f.get("score") is not None:
        sc = f.get("score")
        sc_s = f"{float(sc):.1f} 分" if sc is not None else "—"
        parts.append(
            f'<p class="finding-lead"><b>安全判决：</b>{html_lib.escape(str(f.get("verdict") or "—"))}'
            f' · <b>{html_lib.escape(sc_s)}</b></p>'
        )
    for layer in f.get("defense_layers") or []:
        ln = layer.get("layer", "")
        label = {"static_risk": "L1 静态", "dynamic_intent": "L2 意图", "restricted_exec": "L3 执行"}.get(
            ln, ln
        )
        parts.append(
            f'<p class="finding-item">· {html_lib.escape(label)}：'
            f'{html_lib.escape(str(layer.get("verdict", "—")))} '
            f'{layer.get("score", "—")} 分</p>'
        )
    if f.get("exit_code") is not None:
        ok = f.get("exec_ok")
        st = "成功" if ok else "失败" if ok is False else "—"
        parts.append(
            f'<p class="finding-lead"><b>终端执行：</b>{html_lib.escape(st)} · 退出码 {f.get("exit_code")}</p>'
        )
    out = (f.get("stdout_preview") or "").strip()
    if out:
        prev = html_lib.escape(out[:900]).replace("\n", "<br>")
        parts.append(f'<h3 class="finding-h">输出摘要</h3><div class="report-excerpt">{prev}</div>')
    if f.get("flow") == "secure_exec" and f.get("flow_ok") is None and not f.get("verdict"):
        parts.append(
            '<p class="finding-note">本 Trace 未完整记录 skill_flow_end，以下基于已落库阶段推断。</p>'
        )
    return parts


def _findings_l3_parts(f: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    tools = list(dict.fromkeys(f.get("tools") or []))
    if tools:
        lis = "".join(f"<li><code>{html_lib.escape(t)}</code></li>" for t in tools[:16])
        extra = f"<li>…另有 {len(tools) - 16} 个</li>" if len(tools) > 16 else ""
        parts.append(f'<h3 class="finding-h">调用工具</h3><ul class="finding-rec">{lis}{extra}</ul>')
    llm = int(f.get("llm_calls") or 0)
    tok = int(f.get("tokens") or 0)
    if llm or tok:
        parts.append(
            f'<p class="finding-lead"><b>模型消耗：</b>LLM {llm} 次 · Token {tok}</p>'
        )
    exec_n = sum(1 for s in f.get("timeline") or [] if s.get("name") == "execution")
    if exec_n > 1:
        parts.append(f'<p class="finding-lead"><b>执行轮次：</b>共 {exec_n} 轮 execution（多步工具编排）</p>')
    return parts


def _findings_scan_parts(f: dict[str, Any]) -> list[str]:
    parts: list[str] = []

    health = f.get("health") or {}
    if health:
        cpu = health.get("cpu_percent")
        mem = health.get("memory_percent")
        disk = health.get("disk_percent")
        bits = []
        if cpu is not None:
            bits.append(f"CPU {float(cpu):.1f}%")
        if mem is not None:
            bits.append(f"内存 {float(mem):.1f}%")
        if disk is not None:
            bits.append(f"磁盘 {float(disk):.1f}%")
        if bits:
            parts.append(f'<p class="finding-lead"><b>系统健康：</b>{" · ".join(bits)}</p>')

    listen = f.get("listen_count")
    risky = f.get("risky_ports")
    if listen is not None or risky is not None:
        parts.append(
            f'<p class="finding-lead"><b>端口监听：</b>全网卡监听 {listen or "—"} 个'
            f'；其中高危暴露 <b style="color:#c62828">{risky if risky is not None else "—"}</b> 个</p>'
        )

    items = f.get("risk_items") or []
    if items:
        rows = []
        for r in items[:10]:
            port = r.get("port", "—")
            pid = r.get("pid", "—")
            typ = r.get("type") or "风险"
            local = r.get("local") or ""
            msg = (r.get("message") or "")[:200]
            rows.append(
                "<tr>"
                f"<td>{_level_badge(str(r.get('level', '')))}</td>"
                f"<td>{html_lib.escape(str(typ))}</td>"
                f"<td>{html_lib.escape(str(port))}</td>"
                f"<td>{html_lib.escape(str(pid))}</td>"
                f"<td><code>{html_lib.escape(str(local))}</code></td>"
                f"<td>{html_lib.escape(msg)}</td>"
                "</tr>"
            )
        parts.append(
            '<h3 class="finding-h">风险明细</h3>'
            '<div class="table-scroll"><table class="risk-table">'
            "<thead><tr><th>等级</th><th>类型</th><th>端口</th><th>PID</th><th>监听地址</th><th>说明</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )

    risky_ln = f.get("risky_listeners") or []
    if risky_ln and not items:
        for ln in risky_ln[:8]:
            parts.append(
                f'<p class="finding-item">· 高危监听 <code>{html_lib.escape(str(ln.get("local", "")))}</code>'
                f' PID {html_lib.escape(str(ln.get("pid", "—")))}</p>'
            )

    html_path = f.get("report_html_path") or ""
    if html_path:
        parts.append(
            f'<p class="finding-lead"><b>HTML 报告：</b><code>{html_lib.escape(html_path)}</code></p>'
        )

    excerpt = (f.get("report_excerpt") or "").strip()
    if excerpt:
        body = html_lib.escape(excerpt[:1200]).replace("\n", "<br>")
        parts.append(f'<h3 class="finding-h">报告摘要</h3><div class="report-excerpt">{body}</div>')

    recs: list[str] = []
    ports_seen: set[int] = set()
    for r in items:
        p = r.get("port")
        if p in ports_seen:
            continue
        ports_seen.add(p)
        if p == 5900:
            recs.append(
                "VNC 端口 5900 对 0.0.0.0/:: 监听，建议改为本机回环、加防火墙或停用 vino-server 等远程桌面服务。"
            )
        elif r.get("risky") or str(r.get("level", "")).startswith("高"):
            recs.append(f"核查端口 {p}（PID {r.get('pid', '—')}）业务必要性，并限制监听网卡。")
    if not recs and int(f.get("risk_count") or 0) == 0:
        recs.append("未发现高危项，建议保持定期扫描与端口基线对比。")
    elif not recs:
        recs.append("请根据上表风险项逐项加固，完整步骤见 HTML 报告。")

    if recs:
        lis = "".join(f"<li>{html_lib.escape(x)}</li>" for x in recs[:6])
        parts.append(f'<h3 class="finding-h">处置建议</h3><ul class="finding-rec">{lis}</ul>')

    return parts


def _build_findings_html(f: dict[str, Any]) -> str:
    """所有 Trace 均输出文字分析（不仅 scan_report）."""
    parts: list[str] = [
        f'<p class="finding-lead"><b>结论：</b>{html_lib.escape(_meeting_conclusion(f))}</p>'
    ]
    flow = f.get("flow") or ""
    if flow == "scan_report":
        parts.extend(_findings_scan_parts(f))
    elif flow == "secure_exec":
        parts.extend(_findings_secure_exec_parts(f))
    elif int(f.get("llm_calls") or 0) > 0 or f.get("tools"):
        parts.extend(_findings_l3_parts(f))

    actions = _meeting_actions(f)
    useful = [a for a in actions if "无附加明细" not in a]
    if useful:
        lis = "".join(
            f"<li>{html_lib.escape(a.strip().lstrip('· '))}</li>" for a in useful[:14]
        )
        parts.append(f'<h3 class="finding-h">关键数据</h3><ul class="finding-rec">{lis}</ul>')

    return _findings_wrap("执行分析", parts)


def extract_facts(bundle: dict[str, Any]) -> dict[str, Any]:
    """从卷宗提取结构化要点（TXT 纪要 / HTML 图表共用）."""
    facts: dict[str, Any] = {
        "trace_id": bundle.get("trace_id") or "—",
        "user_message": "",
        "status": "",
        "route": "L3 智能编排",
        "flow": "",
        "flow_ok": None,
        "command": "",
        "verdict": "",
        "score": None,
        "exit_code": None,
        "exec_ok": None,
        "risk_level": "",
        "executed_as_user": "",
        "stdout_preview": "",
        "tools": [],
        "defense_layers": [],
        "llm_calls": 0,
        "tokens": 0,
        "degradation": "",
        "created_at": "",
        "completed_at": "",
        "duration_ms": 0,
        "timeline": [],
        "flow_steps": [],
        "risk_count": None,
        "risky_ports": None,
        "report_len": None,
        "report_html_path": "",
        "risk_by_level": {},
        "risk_items": [],
        "risky_listeners": [],
        "listen_count": None,
        "health": {},
        "report_excerpt": "",
        "alert_event": {},
        "alert_responses": [],
        "alert_occurred_at": "",
    }

    from security_agent.timeutil import format_display, format_storage_timestamp, parse_iso

    st = bundle.get("sqlite_trace") or {}
    facts["user_message"] = (st.get("user_message") or "").strip()
    facts["status"] = st.get("status") or ""
    raw_created = st.get("created_at") or ""
    raw_completed = st.get("completed_at") or ""
    facts["created_at"] = format_storage_timestamp(raw_created) if raw_created else ""
    facts["completed_at"] = format_storage_timestamp(raw_completed) if raw_completed else ""
    meta = _parse_jsonish(st.get("metadata")) or {}
    if isinstance(meta, dict):
        facts["degradation"] = meta.get("degradation_level") or ""

    sqlite_stages = st.get("stages") or []
    stage_deltas = _stage_duration_deltas(sqlite_stages)
    for i, s in enumerate(sqlite_stages):
        name = s.get("name") or s.get("stage") or ""
        data = _parse_jsonish(s.get("data")) or {}
        if not isinstance(data, dict):
            data = {}
        dur = stage_deltas[i] if i < len(stage_deltas) else int(s.get("duration_ms") or 0)
        facts["timeline"].append(
            {
                "name": name,
                "label": _STAGE_LABELS.get(name, name),
                "ms": dur,
                "data": data,
                "at": format_storage_timestamp(s.get("timestamp")) if s.get("timestamp") else "",
            }
        )
        if name == "skill_flow_start":
            flow = data.get("flow") or ""
            facts["flow"] = flow
            facts["route"] = f"L2 · {_FLOW_DISPLAY.get(flow, flow or 'Skill 流程')}"
        if name == "skill_flow_end":
            _ingest_skill_flow_payload(facts, data)
            facts["flow_ok"] = data.get("ok")
            facts["flow"] = facts["flow"] or data.get("flow", "")
            for k in ("command", "verdict", "exit_code", "exec_ok"):
                if data.get(k) is not None:
                    facts[k] = data[k]
            if data.get("score") is not None:
                facts["score"] = data["score"]
        if name == "post_verify":
            facts["exec_ok"] = data.get("ok", facts["exec_ok"])
            if data.get("exit_code") is not None:
                facts["exit_code"] = data["exit_code"]
            msg = (data.get("message") or "").strip()
            if msg:
                facts["stdout_preview"] = msg

    rep = bundle.get("reasoning_report") or {}
    if rep:
        facts["user_message"] = facts["user_message"] or (rep.get("user_message") or "").strip()
        facts["llm_calls"] = int(rep.get("llm_calls") or 0)
        facts["tokens"] = int(rep.get("tokens_used") or 0)
        for a in rep.get("actions") or []:
            tn = a.get("tool_name") or a.get("name")
            if tn:
                facts["tools"].append(tn)
        for thought in rep.get("thoughts") or []:
            content = str(thought.get("content") or "")
            m = re.search(r"['\"]tool['\"]\s*:\s*['\"]([^'\"]+)['\"]", content)
            if m:
                facts["tools"].append(m.group(1))
        if facts["tools"]:
            facts["tools"] = list(dict.fromkeys(facts["tools"]))

    for entry in bundle.get("audit_events") or []:
        action = entry.get("action") or ""
        detail = _parse_jsonish(entry.get("detail")) or {}
        if not isinstance(detail, dict):
            continue
        # trace_stage:xxx 的 payload 在 detail.detail
        if action.startswith("trace_stage:") and isinstance(detail.get("detail"), dict):
            stage_name = detail.get("stage") or action.split(":", 1)[-1]
            detail = detail["detail"]
            action = stage_name
        if action == "skill_flow_start":
            facts["flow"] = detail.get("flow") or facts["flow"]
            if facts["flow"]:
                facts["route"] = f"L2 · {_FLOW_DISPLAY.get(facts['flow'], facts['flow'])}"
        elif action == "skill_flow_end":
            _ingest_skill_flow_payload(facts, detail)
            facts["flow_ok"] = detail.get("ok", facts["flow_ok"])
            defense = detail.get("defense") or {}
            wrap = detail.get("execution") or {}
            if not defense and isinstance(wrap.get("defense_result"), dict):
                defense = wrap["defense_result"]
            if defense:
                facts["verdict"] = facts["verdict"] or str(defense.get("overall_verdict", ""))
                if facts["score"] is None:
                    facts["score"] = defense.get("overall_score")
                if defense.get("layers"):
                    facts["defense_layers"] = defense["layers"]
            exec_res = wrap.get("execution_result") if isinstance(wrap.get("execution_result"), dict) else {}
            if exec_res:
                facts["exec_ok"] = exec_res.get("ok", facts["exec_ok"])
                facts["exit_code"] = exec_res.get("exit_code", facts["exit_code"])
                out = (exec_res.get("stdout") or "").strip()
                if out:
                    facts["stdout_preview"] = out
            if detail.get("command"):
                facts["command"] = detail["command"]
        elif detail.get("command") and "exit_code" in detail:
            facts["command"] = facts["command"] or detail.get("command", "")
            facts["exit_code"] = detail.get("exit_code", facts["exit_code"])
            facts["risk_level"] = detail.get("risk_level") or facts["risk_level"]
            facts["executed_as_user"] = detail.get("executed_as_user") or facts["executed_as_user"]

    m = re.search(r"`([^`]+)`", facts["user_message"])
    if m and not facts["command"]:
        facts["command"] = m.group(1).strip()

    if facts["llm_calls"] == 0 and facts["flow"]:
        facts["route_note"] = "未调用大模型（L2 确定性流程）"
    elif facts["llm_calls"]:
        facts["route_note"] = f"LLM {facts['llm_calls']} 次 · Token {facts['tokens']}"

    if facts["timeline"]:
        facts["duration_ms"] = sum(int(s.get("ms") or 0) for s in facts["timeline"])
    start_dt = parse_iso(raw_created)
    end_dt = parse_iso(raw_completed)
    if start_dt and end_dt and end_dt >= start_dt:
        facts["duration_ms"] = max(
            facts["duration_ms"],
            int((end_dt - start_dt).total_seconds() * 1000),
        )

    ae = facts.get("alert_event") or {}
    if isinstance(ae, dict) and ae.get("ts"):
        facts["alert_occurred_at"] = format_display(ae.get("ts"))

    return facts


def _meeting_conclusion(f: dict[str, Any]) -> str:
    if f.get("flow") == "secure_exec":
        v = f.get("verdict") or "—"
        sc = f.get("score")
        sc_s = f"，安全评分 {float(sc):.1f}" if sc is not None else ""
        cmd = f.get("command") or "—"
        ok = "已成功执行" if f.get("exit_code") == 0 or f.get("exec_ok") else "执行结果待确认"
        return f"对用户指令「{f.get('user_message', '')[:80]}」完成三层防御评估，判决 {v}{sc_s}；命令 `{cmd}` {ok}。"
    if f.get("flow") == "alert_response":
        n = len(f.get("alert_responses") or [])
        occ = f.get("alert_occurred_at") or ""
        occ_s = f"（告警发生 {occ}）" if occ else ""
        st = "已完成" if f.get("flow_ok") else "未完全完成"
        return f"对告警事件完成 L2 路由处置，{st}；共 {n} 个 Skill 响应{occ_s}。"
    if f.get("flow") == "scan_report":
        rc = f.get("risk_count")
        rc_s = f"共发现 {rc} 项风险" if rc is not None else "风险项待统计"
        ports = f.get("risky_ports")
        port_s = f"，暴露高危端口 {ports} 个" if ports not in (None, 0) else ""
        html = f.get("report_html_path") or ""
        html_s = f"；HTML 报告已生成（{html.split('/')[-1]}）" if html else ""
        st = "已完成" if f.get("flow_ok") else "未完全完成"
        return f"按用户要求生成扫描报告，{st}。{rc_s}{port_s}{html_s}。"
    if f.get("flow"):
        st = "已完成" if f.get("flow_ok") else "未完全完成"
        return f"对用户指令完成 L2 流程「{_FLOW_DISPLAY.get(f['flow'], f['flow'])}」，{st}。"
    if f.get("tools"):
        return f"经 L3 智能编排调用 {len(set(f['tools']))} 类工具后完成分析。"
    return f"请求已处理，状态 {f.get('status') or 'completed'}。"


def _meeting_process(f: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    skip = {"incident_spine_begin", "incident_spine_end"}
    n = 0
    for s in f.get("timeline") or []:
        if s.get("name") in skip:
            continue
        n += 1
        ms = s.get("ms")
        ms_s = f"，耗时 {ms}ms" if ms else ""
        at = s.get("at") or ""
        at_s = f" @ {at}" if at else ""
        lines.append(f"  {n}. {s.get('label')}{ms_s}{at_s}")
        if n >= 10:
            break
    return lines or ["  （无阶段记录）"]


def _meeting_actions(f: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if f.get("command"):
        lines.append(f"  · 执行命令：{f['command']}")
    if f.get("verdict"):
        sc = f.get("score")
        lines.append(f"  · 安全判决：{f['verdict']}" + (f"（{float(sc):.1f} 分）" if sc is not None else ""))
    for layer in f.get("defense_layers") or []:
        ln = layer.get("layer", "")
        label = {"static_risk": "L1", "dynamic_intent": "L2", "restricted_exec": "L3"}.get(ln, ln)
        lines.append(f"  · {label}：{layer.get('verdict')} {layer.get('score')} 分")
    if f.get("exit_code") is not None:
        lines.append(f"  · 退出码：{f['exit_code']}")
    if f.get("executed_as_user"):
        lines.append(f"  · 执行用户：{f['executed_as_user']}")
    if f.get("flow") == "alert_response":
        if f.get("alert_occurred_at"):
            lines.append(f"  · 告警发生时间：{f['alert_occurred_at']}")
        if f.get("completed_at"):
            lines.append(f"  · 处置完成时间：{f['completed_at']}")
        for i, r in enumerate((f.get("alert_responses") or [])[:12], 1):
            if isinstance(r, dict):
                skill = r.get("skill") or r.get("name") or "skill"
                plan = r.get("plan_summary") if isinstance(r.get("plan_summary"), dict) else {}
                summary = (r.get("summary") or r.get("message") or r.get("status") or "")[:160]
                rc = plan.get("root_cause") or r.get("root_cause")
                if rc:
                    summary = f"根因: {rc}"
                elif r.get("recommendation"):
                    summary = str(r["recommendation"])[:160]
                lines.append(f"  · [{i}] {skill}：{summary or '—'}")
        for st in f.get("flow_steps") or []:
            label = _FLOW_STEP_CN.get(st.get("step") or "", st.get("step") or "步骤")
            dms = st.get("duration_ms")
            extra = f" {dms}ms" if dms is not None else ""
            mark = "✓" if st.get("ok", True) else "✗"
            lines.append(f"  · [{mark}] {label}{extra}")
    if f.get("flow") == "scan_report":
        if f.get("risk_count") is not None:
            lines.append(f"  · 风险项：{f['risk_count']}")
        if f.get("risky_ports") is not None:
            lines.append(f"  · 高危暴露端口：{f['risky_ports']}")
        for lv, cnt in sorted((f.get("risk_by_level") or {}).items()):
            lines.append(f"  · 风险等级 {lv}：{cnt}")
        if f.get("report_len"):
            lines.append(f"  · 文本报告长度：{f['report_len']} 字符")
        if f.get("report_html_path"):
            lines.append(f"  · HTML：{f['report_html_path']}")
        for st in f.get("flow_steps") or []:
            step = st.get("step") or ""
            label = _FLOW_STEP_CN.get(step, step)
            extra = ""
            if st.get("risk_count") is not None:
                extra = f" 风险 {st['risk_count']}"
            elif st.get("risky_count") is not None:
                extra = f" 暴露 {st['risky_count']}"
            elif st.get("report_len") is not None:
                extra = f" 报告 {st['report_len']} 字"
            elif st.get("path"):
                extra = f" → {st['path']}"
            mark = "✓" if st.get("ok", True) else "✗"
            lines.append(f"  · [{mark}] {label}{extra}")
    if f.get("tools"):
        uniq = list(dict.fromkeys(f["tools"]))
        lines.append(f"  · 调用工具：{', '.join(uniq[:10])}" + (f" 等 {len(uniq)} 个" if len(uniq) > 10 else ""))
    return lines or ["  · （无附加明细）"]


def _meeting_followup(f: dict[str, Any]) -> list[str]:
    lines = [
        "  · 本纪要由 Trace 自动生成，供值班交接与审计留档。",
        "  · 可视化耗时/评分/工具统计请打开同 Trace 的 HTML 分析报告。",
    ]
    if f.get("flow") == "secure_exec" and f.get("exit_code") == 0:
        lines.insert(0, "  · 若需留存终端完整输出，请在助手对话中复制或导出 JSON（调试）。")
    if f.get("llm_calls", 0) > 5:
        lines.insert(0, "  · 本次 L3 工具调用较多，可考虑改用 L2 固定流程或缩小提问范围以节省 Token。")
    return lines


def bundle_to_text(bundle: dict[str, Any]) -> str:
    """执行纪要（TXT）— 会议纪要体，无图表."""
    f = extract_facts(bundle)
    lines = [
        "",
        "                    安全运维 Agent · 执行纪要",
        "",
        "—" * 52,
        f"纪要编号：{f['trace_id']}",
        f"记录时间：{f.get('created_at') or '—'}  至  {f.get('completed_at') or '—'}",
        f"执行路径：{f.get('route', '—')}",
    ]
    if f.get("route_note"):
        lines.append(f"编      制：{f['route_note']}")
    if f.get("degradation") and f.get("degradation") != "S0":
        lines.append(f"降级级别：{f['degradation']}")
    lines.extend(
        [
            "",
            "一、议题与结论",
            "—" * 52,
            f"  {_meeting_conclusion(f)}",
            "",
            "二、处置过程（按时间）",
            "—" * 52,
        ]
    )
    lines.extend(_meeting_process(f))
    lines.extend(
        [
            "",
            "三、关键动作与数据",
            "—" * 52,
        ]
    )
    lines.extend(_meeting_actions(f))
    out = (f.get("stdout_preview") or "").strip()
    if out:
        lines.append("  · 终端输出摘要（前若干行）：")
        for ln in out.splitlines()[:12]:
            lines.append(f"      {ln}")
        if out.count("\n") > 12:
            lines.append("      …")
    lines.extend(
        [
            "",
            "四、后续建议",
            "—" * 52,
        ]
    )
    lines.extend(_meeting_followup(f))
    lines.extend(["", "—" * 52, "（完）", ""])
    return "\n".join(lines)


def _summary_rows_for_flow(f: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [
        ("用户请求", f.get("user_message") or "—"),
        ("执行路径", f.get("route") or "—"),
        ("流程类型", f.get("flow") or "L3"),
    ]
    flow = f.get("flow")
    if flow == "scan_report":
        rows.extend(
            [
                ("风险项", str(f.get("risk_count")) if f.get("risk_count") is not None else "—"),
                ("高危暴露端口", str(f.get("risky_ports")) if f.get("risky_ports") is not None else "—"),
                ("文本报告", f"{f.get('report_len')} 字符" if f.get("report_len") else "—"),
                ("HTML 报告", (f.get("report_html_path") or "—").split("/")[-1] or "—"),
                ("流程结果", "成功" if f.get("flow_ok") else "未完全成功"),
            ]
        )
    elif flow == "secure_exec":
        rows.extend(
            [
                (
                    "安全判决",
                    (f"{f.get('verdict') or '—'}" + (f" / {float(f['score']):.1f}分" if f.get("score") is not None else ""))
                    if (f.get("verdict") or f.get("score") is not None)
                    else ("allow（推断）" if f.get("exit_code") == 0 else "—"),
                ),
                ("命令", f.get("command") or "—"),
                ("退出码", str(f.get("exit_code")) if f.get("exit_code") is not None else "—"),
            ]
        )
    else:
        rows.append(
            (
                "安全判决",
                (f"{f.get('verdict') or '—'}" + (f" / {float(f['score']):.1f}分" if f.get("score") is not None else ""))
                if (f.get("verdict") or f.get("score") is not None)
                else "—",
            )
        )
        rows.append(("命令", f.get("command") or "—"))
        rows.append(("退出码", str(f.get("exit_code")) if f.get("exit_code") is not None else "—"))
    rows.append(("LLM", f"{f.get('llm_calls', 0)} 次 / {f.get('tokens', 0)} tokens"))
    return rows


def bundle_to_html(bundle: dict[str, Any]) -> str:
    """可视化分析报告（HTML）— matplotlib 图表 + 要点摘要."""
    f = extract_facts(bundle)
    tid = html_lib.escape(str(f["trace_id"]))
    sections = build_visual_sections(f, bundle)
    chart_blocks = [
        f'<section class="chart"><h3>{html_lib.escape(title)}</h3>{body}</section>'
        for title, body in sections
    ]
    if not chart_blocks:
        chart_blocks.append('<p class="warn">本 Trace 无足够数据生成图表。</p>')

    summary_rows = _summary_rows_for_flow(f)
    table_html = "".join(
        f"<tr><th>{html_lib.escape(k)}</th><td>{html_lib.escape(str(v))}</td></tr>"
        for k, v in summary_rows
    )

    charts_html = "\n".join(chart_blocks)
    findings_html = _build_findings_html(f)
    strategy_html = build_viz_strategy_html(f, bundle)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trace 可视化分析 · {tid}</title>
<style>
body{{font-family:"PingFang SC","Microsoft YaHei",sans-serif;margin:0;padding:20px;background:#eef2f7;color:#1e293b;}}
.wrap{{max-width:960px;margin:0 auto;}}
header{{background:linear-gradient(135deg,#0d47a1,#1565c0);color:#fff;padding:20px 24px;border-radius:10px;margin-bottom:16px;}}
header h1{{margin:0 0 8px;font-size:20px;}}
header p{{margin:4px 0;font-size:13px;opacity:.92;}}
.panel{{background:#fff;border-radius:10px;padding:16px 20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.06);}}
table{{width:100%;border-collapse:collapse;font-size:14px;}}
th{{text-align:left;width:120px;padding:8px 10px;background:#f1f5f9;color:#475569;}}
td{{padding:8px 10px;border-bottom:1px solid #e2e8f0;}}
.charts{{display:flex;flex-direction:column;gap:16px;}}
.chart{{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 4px rgba(0,0,0,.06);width:100%;box-sizing:border-box;overflow:hidden;}}
.chart h3{{margin:0 0 10px;font-size:14px;color:#1565c0;}}
.chart-def{{margin:0 0 6px;font-size:12px;color:#64748b;line-height:1.5;}}
.chart-meta{{margin:0 0 10px;font-size:11px;color:#94a3b8;}}
.chart img{{width:100%;max-width:100%;height:auto;display:block;}}
.svg-chart{{font-size:13px;max-width:100%;overflow-x:auto;}}
.bar-row{{display:flex;align-items:center;margin:8px 0;gap:8px;max-width:100%;}}
.bar-label{{flex:0 0 88px;max-width:88px;color:#475569;font-size:12px;line-height:1.3;word-break:break-all;}}
.bar-track{{flex:1;min-width:0;display:flex;align-items:center;gap:6px;}}
.bar-fill{{height:16px;border-radius:4px;max-width:100%;}}
.bar-val{{font-size:12px;color:#334155;flex-shrink:0;}}
.plot-h{{margin:6px 0 10px;}}
.plot-grid-3{{display:grid;grid-template-columns:108px 1fr 56px;gap:10px;align-items:center;}}
.plot-grid-2{{display:grid;grid-template-columns:108px 1fr;gap:10px;align-items:center;}}
.plot-h-head{{margin-bottom:4px;}}
.plot-label{{font-size:12px;color:#475569;line-height:1.35;word-break:break-all;}}
.plot-val{{font-size:12px;color:#334155;text-align:right;font-weight:600;}}
.plot-col{{position:relative;height:24px;background:#e2e8f0;border-radius:4px;overflow:hidden;}}
.plot-col-axis{{height:auto;background:transparent;overflow:visible;min-height:32px;}}
.axis-x-rail{{position:relative;height:20px;width:100%;}}
.axis-x-line{{height:1px;background:#64748b;width:100%;margin:2px 0 0;}}
.axis-tick{{position:absolute;transform:translateX(-50%);font-size:10px;color:#64748b;white-space:nowrap;top:2px;}}
.axis-unit-inline{{position:absolute;right:0;top:2px;font-size:10px;color:#94a3b8;}}
.axis-track-grid{{position:absolute;left:0;right:0;top:0;bottom:0;pointer-events:none;}}
.axis-gridline{{position:absolute;top:0;bottom:0;width:1px;background:#cbd5e1;transform:translateX(-50%);}}
.bar-fill-h{{height:100%;border-radius:4px;min-width:2px;}}
.gantt-inner{{display:flex;align-items:center;padding-left:8px;font-size:11px;color:#fff;min-width:28px;box-sizing:border-box;}}
.bullet-threshold{{position:absolute;top:0;bottom:0;width:2px;background:#c62828;z-index:2;}}
.plot-row{{margin:8px 0;}}
.scale-hint{{font-size:11px;color:#94a3b8;margin:4px 0 0;}}
.plot-v{{display:flex;align-items:flex-end;gap:10px;margin:8px 0;}}
.plot-v-y{{position:relative;width:44px;height:118px;flex-shrink:0;}}
.plot-v-body{{flex:1;overflow-x:auto;}}
.axis-y-line{{position:absolute;right:6px;top:0;bottom:0;width:1px;background:#64748b;}}
.axis-y-rail{{position:absolute;right:8px;top:0;bottom:0;left:0;}}
.axis-tick-y{{position:absolute;right:0;transform:translateY(50%);font-size:10px;color:#64748b;text-align:right;}}
.axis-unit-y{{position:absolute;left:0;top:-14px;font-size:9px;color:#94a3b8;}}
.axis-line{{stroke:#64748b;stroke-width:1.2;}}
.axis-grid{{stroke:#e2e8f0;stroke-width:1;}}
.axis-tick-svg{{font-size:10px;fill:#64748b;}}
.axis-unit-svg{{font-size:10px;fill:#94a3b8;}}
.vbar-chart{{display:flex;align-items:flex-end;justify-content:center;gap:14px;min-height:130px;padding-top:4px;}}
.vbar-item{{display:flex;flex-direction:column;align-items:center;flex:0 1 76px;}}
.vbar-col{{width:44px;height:110px;background:#e2e8f0;border-radius:6px;display:flex;align-items:flex-end;overflow:hidden;}}
.vbar-fill{{width:100%;border-radius:6px 6px 0 0;}}
.vbar-val-top{{font-size:12px;font-weight:600;color:#334155;margin-bottom:4px;}}
.vbar-label{{font-size:11px;color:#64748b;text-align:center;margin-top:4px;max-width:72px;line-height:1.25;}}
.donut-wrap{{padding:8px 0;}}
.donut-panel{{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start;justify-content:center;}}
.donut{{width:140px;height:140px;border-radius:50%;position:relative;flex-shrink:0;}}
.donut-hole{{position:absolute;inset:28px;background:#fff;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:12px;}}
.donut-hole b{{font-size:18px;color:#1565c0;}}
.donut-side{{min-width:160px;}}
.scale-box,.radar-scale-box{{background:#f8fafc;border-radius:8px;padding:10px 12px;font-size:12px;color:#475569;margin-bottom:10px;}}
.scale-box b,.radar-scale-box b{{color:#1565c0;display:block;margin-bottom:6px;}}
.scale-box ul,.radar-scale-box ul{{margin:0;padding-left:18px;line-height:1.6;}}
.donut-legend{{display:flex;flex-direction:column;gap:6px;font-size:13px;}}
.donut-leg i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;}}
.radar-layout{{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start;justify-content:center;}}
.radar-chart{{width:220px;height:auto;flex-shrink:0;}}
.radar-lbl{{font-size:10px;fill:#475569;font-weight:600;}}
.radar-score{{font-size:11px;fill:#1565c0;font-weight:700;}}
.radar-grid{{fill:none;stroke:#cbd5e1;stroke-width:1;}}
.radar-fill{{fill:rgba(21,101,192,.2);stroke:#1565c0;stroke-width:2;}}
.stat-row{{display:flex;flex-wrap:wrap;gap:12px;}}
.stat-card{{flex:1;min-width:140px;background:#f8fafc;border-radius:10px;padding:16px;border-left:4px solid;text-align:center;}}
.stat-card b{{display:block;font-size:26px;margin-bottom:4px;}}
.stat-card span{{font-size:12px;color:#64748b;}}
.line-chart{{width:100%;max-width:520px;height:auto;display:block;margin:0 auto;}}
.viz-strategy .strategy-list{{margin:8px 0 0;padding-left:20px;font-size:13px;color:#475569;line-height:1.7;}}
.step-table{{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed;}}
.step-table th,.step-table td{{padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top;word-wrap:break-word;}}
.step-table th{{background:#f8fafc;color:#475569;font-weight:600;width:22%;}}
.step-table td:nth-child(2){{width:12%;}}
.findings-panel .finding-lead{{margin:0 0 10px;font-size:14px;line-height:1.55;}}
.findings-panel .finding-h{{margin:14px 0 8px;font-size:14px;color:#0d47a1;}}
.table-scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;}}
.risk-table{{width:100%;min-width:520px;border-collapse:collapse;font-size:13px;}}
.risk-table th,.risk-table td{{padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top;}}
.risk-table th{{background:#f8fafc;color:#475569;white-space:nowrap;}}
.risk-table code{{font-size:12px;word-break:break-all;}}
.badge-lv{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;}}
.badge-lv.risk-high{{background:#ffebee;color:#c62828;}}
.badge-lv.risk-med{{background:#fff3e0;color:#e65100;}}
.badge-lv.risk-low{{background:#e8f5e9;color:#2e7d32;}}
.finding-rec{{margin:0;padding-left:20px;color:#334155;line-height:1.6;}}
.finding-note{{margin:8px 0 0;font-size:12px;color:#e65100;}}
.finding-item{{margin:4px 0;font-size:13px;color:#475569;}}
.report-excerpt{{background:#f8fafc;border-radius:8px;padding:12px;font-size:13px;color:#475569;line-height:1.55;max-height:240px;overflow-y:auto;}}
.badge-chart{{padding:12px;text-align:center;}}
.badge{{display:inline-block;padding:8px 20px;border-radius:8px;font-weight:600;font-size:15px;}}
.badge.ok{{background:#e8f5e9;color:#2e7d32;}}
.badge.fail{{background:#ffebee;color:#c62828;}}
.score{{display:block;margin-top:8px;font-size:22px;color:#1565c0;}}
.kpi-row{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:8px;}}
.kpi{{flex:1;min-width:120px;background:#f8fafc;border-radius:8px;padding:12px;text-align:center;}}
.kpi b{{display:block;font-size:22px;color:#1565c0;}}
.kpi span{{font-size:12px;color:#64748b;}}
.warn{{color:#c62828;font-size:13px;}}
footer{{font-size:12px;color:#64748b;text-align:center;margin-top:12px;}}
</style></head><body><div class="wrap">
<header>
  <h1>执行溯源 · 可视化分析报告</h1>
  <p>Trace ID：{tid}</p>
  <p>时间：{html_lib.escape(str(f.get('created_at') or '—'))} → {html_lib.escape(str(f.get('completed_at') or '—'))}</p>
  <p>{html_lib.escape(str(f.get('route_note') or ''))}</p>
</header>
<section class="panel"><h2 style="margin:0 0 12px;font-size:16px;">数据摘要</h2>
<table>{table_html}</table></section>
{findings_html}
{strategy_html}
<div class="charts">{charts_html}</div>
<footer>纪要全文请导出 TXT；原始卷宗请导出 JSON（调试）。</footer>
</div></body></html>"""

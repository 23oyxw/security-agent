"""Format tool outputs into human-readable ops summaries without LLM."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_tool_payload(raw: Any) -> Any:
    """Parse tool return value (JSON string, dict, or list)."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw).strip()
    if not text or text.startswith(("工具", "规则", "需要用户", "L2")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        import ast
        return ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return text


_parse_payload = parse_tool_payload


def _pct_bar(pct: float, width: int = 12) -> str:
    p = max(0.0, min(100.0, float(pct or 0)))
    filled = int(round(p * width / 100))
    return "#" * filled + "-" * (width - filled)


def _health_level(pct: float) -> str:
    if pct >= 90:
        return "critical"
    if pct >= 75:
        return "high"
    if pct >= 50:
        return "ok"
    return "good"


def _format_health_block(data: dict[str, Any]) -> list[str]:
    lines = ["## System resources"]
    cpu = float(data.get("cpu_percent", 0))
    mem = float(data.get("memory_percent", 0))
    disk = float(data.get("disk_percent", 0))
    lines.append(f"- CPU {cpu:.1f}% [{_pct_bar(cpu)}] ({_health_level(cpu)})")
    lines.append(
        f"- Memory {mem:.1f}% [{_pct_bar(mem)}], available {data.get('memory_available_gb', '?')} GB"
    )
    lines.append(
        f"- Disk {disk:.1f}% [{_pct_bar(disk)}], free {data.get('disk_free_gb', '?')} GB"
    )
    platform = data.get("platform", "")
    elevated = data.get("elevated")
    if platform:
        role = "elevated" if elevated else "user"
        if elevated is None:
            role = ""
        lines.append(f"- Platform {platform}" + (f" ({role})" if role else ""))
    return lines


def _format_processes_block(data: Any) -> list[str]:
    rows = data if isinstance(data, list) else (data.get("processes") if isinstance(data, dict) else None)
    if not isinstance(rows, list) or not rows:
        return []
    lines = ["## 进程（CPU Top）"]
    sorted_rows = sorted(
        [r for r in rows if isinstance(r, dict)],
        key=lambda r: float(r.get("cpu_percent") or r.get("cpu") or 0),
        reverse=True,
    )[:8]
    for r in sorted_rows:
        pid = r.get("pid", "?")
        name = r.get("name", r.get("process", "?"))
        cpu = r.get("cpu_percent", r.get("cpu", 0))
        mem = r.get("memory_percent", r.get("mem", 0))
        lines.append(f"- PID {pid} {name}: CPU {cpu}%, mem {mem}%")
    if len(rows) > 8:
        lines.append(f"- ... and {len(rows) - 8} more")
    return lines


def _format_ports_block(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    lines = ["## 端口暴露"]
    risky = int(data.get("risky_count") or len(data.get("alerts") or []))
    listening = data.get("listener_count") or data.get("listening_count") or data.get("total_listening")
    if listening is not None:
        lines.append(f"- 监听 {listening} 个，高危 {risky} 个")
    elif risky:
        lines.append(f"- Risky exposures: {risky}")
    else:
        lines.append("- 未检测到高危端口暴露")
    for alert in (data.get("alerts") or [])[:5]:
        if isinstance(alert, dict):
            port = alert.get("port", alert.get("local_port", "?"))
            reason = alert.get("message", alert.get("reason", ""))
            lines.append(f"  - 端口 {port}: {reason}")
    return lines


def collect_tool_outputs(
    tool_trace: list[dict[str, Any]] | None = None,
    parallel_result: dict[str, Any] | None = None,
    tool_out_text: str = "",
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if parallel_result:
        for name, raw in (parallel_result.get("results") or {}).items():
            parsed = _parse_payload(raw)
            if parsed is not None:
                out[name] = parsed
    if tool_trace:
        for entry in tool_trace:
            name = entry.get("tool")
            if not name:
                continue
            parsed = entry.get("parsed")
            if parsed is None:
                raw = entry.get("output")
                if raw is None:
                    continue
                parsed = _parse_payload(raw)
            if isinstance(parsed, (dict, list)):
                out[name] = parsed
    if tool_out_text and not out:
        for m in re.finditer(r"###\s+(\w+)\s*\n([\s\S]*?)(?=###\s+\w+|\Z)", tool_out_text):
            name, body = m.group(1), m.group(2).strip()
            parsed = _parse_payload(body)
            if parsed is not None:
                out[name] = parsed
    return out


def format_health_summary(
    tool_data: dict[str, Any],
    *,
    intent: str = "health",
    trace_id: str = "",
    degraded: bool = False,
    summary_mode: str = "auto",
) -> str:
    lines: list[str] = []
    if summary_mode == "deterministic":
        title = "系统健康摘要 · 本地工具采集"
    elif degraded:
        title = "系统健康摘要 · 本地工具采集（降级）"
    else:
        title = "系统健康摘要"
    lines.append(f"【{title}】")
    if trace_id:
        lines.append(f"trace: {trace_id}")
    lines.append("")

    health = tool_data.get("get_system_health")
    if isinstance(health, dict):
        cpu = float(health.get("cpu_percent", 0))
        mem = float(health.get("memory_percent", 0))
        disk = float(health.get("disk_percent", 0))
        lines.append("## 系统资源")
        lines.append(f"- CPU {cpu:.1f}%")
        lines.append(f"- 内存 {mem:.1f}% (可用 {health.get('memory_available_gb', '?')} GB)")
        lines.append(f"- 磁盘 {disk:.1f}% (剩余 {health.get('disk_free_gb', '?')} GB)")
        if health.get("platform"):
            lines.append(f"- 平台 {health.get('platform')}")

    procs = tool_data.get("list_processes")
    if procs is not None:
        block = _format_processes_block(procs)
        if block:
            lines.append("")
            lines.extend(block)

    ports = tool_data.get("check_exposed_ports")
    if ports is not None:
        block = _format_ports_block(ports)
        if block:
            lines.append("")
            lines.extend(block)

    if len(lines) <= 2:
        return ""

    if degraded and summary_mode != "deterministic":
        lines.append("")
        lines.append("说明: 大模型暂不可用，以上为本地只读工具采集结果。")
    return "\n".join(lines)


def format_tool_outputs_for_user(
    intent: str,
    tool_out: str = "",
    tool_trace: list[dict[str, Any]] | None = None,
    *,
    trace_id: str = "",
    degraded: bool = False,
    summary_mode: str = "auto",
    parallel_result: dict[str, Any] | None = None,
) -> str:
    data = collect_tool_outputs(tool_trace, parallel_result, tool_out)
    if intent in ("health", "monitor_status", "parallel_info", "processes", "general"):
        text = format_health_summary(
            data,
            intent=intent,
            trace_id=trace_id,
            degraded=degraded,
            summary_mode=summary_mode,
        )
        if text:
            return text
    if not data:
        return ""
    lines = [f"【工具采集】意图: {intent}"]
    if trace_id:
        lines.append(f"trace: {trace_id}")
    for name, payload in data.items():
        snippet = json.dumps(payload, ensure_ascii=False)[:400]
        lines.append(f"\n{name}: {snippet}")
    return "\n".join(lines)

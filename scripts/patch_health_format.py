"""Patch health_format.py in-place (UTF-8 safe, ASCII-only script)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "security_agent" / "agent" / "health_format.py"
SRC = ROOT / "scripts" / "_health_format_src.py"


def main() -> None:
    raw = TARGET.read_bytes()
    if b"\x00" in raw[:80]:
        text = raw.decode("utf-16-le")
    else:
        text = raw.decode("utf-8")

    if "def parse_tool_payload" not in text:
        text = text.replace(
            "def _parse_payload(raw: Any) -> Any:",
            "def parse_tool_payload(raw: Any) -> Any:\n    return _parse_payload(raw)\n\n\ndef _parse_payload(raw: Any) -> Any:",
            1,
        )

    text = text.replace("## Top processes (CPU)", "## \u8fdb\u7a0b\uff08CPU Top\uff09")
    text = text.replace("## Port exposure", "## \u7aef\u53e3\u66b4\u9732")

    old_ports = (
        '    listening = data.get("listening_count") or data.get("total_listening")\n'
        '    if listening is not None:\n'
        '        lines.append(f"- Listening {listening}, risky {risky}")\n'
        '    elif risky:\n'
        '        lines.append(f"- Risky exposures: {risky}")\n'
        '    else:\n'
        '        lines.append("- No high-risk exposure detected")\n'
        '    for alert in (data.get("alerts") or [])[:5]:\n'
        '        if isinstance(alert, dict):\n'
        '            port = alert.get("port", alert.get("local_port", "?"))\n'
        '            reason = alert.get("reason", alert.get("message", ""))\n'
        '            lines.append(f"  - port {port}: {reason}")'
    )
    new_ports = (
        '    listening = data.get("listener_count") or data.get("listening_count") or data.get("total_listening")\n'
        '    if listening is not None:\n'
        '        lines.append(f"- \u76d1\u542c {listening} \u4e2a\uff0c\u9ad8\u5371 {risky} \u4e2a")\n'
        '    elif risky:\n'
        '        lines.append(f"- \u9ad8\u5371\u66b4\u9732: {risky} \u4e2a")\n'
        '    else:\n'
        '        lines.append("- \u672a\u68c0\u6d4b\u5230\u9ad8\u5371\u7aef\u53e3\u66b4\u9732")\n'
        '    for alert in (data.get("alerts") or [])[:5]:\n'
        '        if isinstance(alert, dict):\n'
        '            port = alert.get("port", alert.get("local_port", "?"))\n'
        '            reason = alert.get("message", alert.get("reason", ""))\n'
        '            lines.append(f"  - \u7aef\u53e3 {port}: {reason}")'
    )
    text = text.replace(old_ports, new_ports)

    old_collect = (
        '            raw = entry.get("output")\n'
        '            if raw is None:\n'
        '                continue\n'
        '            parsed = _parse_payload(raw)\n'
        '            if parsed is not None:\n'
        '                out[name] = parsed'
    )
    new_collect = (
        '            parsed = entry.get("parsed")\n'
        '            if parsed is None:\n'
        '                raw = entry.get("output")\n'
        '                if raw is None:\n'
        '                    continue\n'
        '                parsed = _parse_payload(raw)\n'
        '            if isinstance(parsed, (dict, list)):\n'
        '                out[name] = parsed'
    )
    text = text.replace(old_collect, new_collect)

    old_fmt = (
        '    degraded: bool = False,\n'
        ') -> str:\n'
        '    lines: list[str] = []\n'
        '    title = "\u7cfb\u7edf\u5065\u5eb7\u6458\u8981"\n'
        '    if degraded:\n'
        '        title += " (\u672c\u5730\u5de5\u5177\u91c7\u96c6)"\n'
        '    lines.append(f"\u3010{title}\u3011")'
    )
    new_fmt = (
        '    degraded: bool = False,\n'
        '    summary_mode: str = "auto",\n'
        ') -> str:\n'
        '    lines: list[str] = []\n'
        '    if summary_mode == "deterministic":\n'
        '        title = "\u7cfb\u7edf\u5065\u5eb7\u6458\u8981 \u00b7 \u672c\u5730\u5de5\u5177\u91c7\u96c6"\n'
        '    elif degraded:\n'
        '        title = "\u7cfb\u7edf\u5065\u5eb7\u6458\u8981 \u00b7 \u672c\u5730\u5de5\u5177\u91c7\u96c6\uff08\u964d\u7ea7\uff09"\n'
        '    else:\n'
        '        title = "\u7cfb\u7edf\u5065\u5eb7\u6458\u8981"\n'
        '    lines.append(f"\u3010{title}\u3011")'
    )
    text = text.replace(old_fmt, new_fmt)

    text = text.replace(
        '    lines.append("")\n'
        '    if degraded:\n'
        '        lines.append("\u8bf4\u660e: \u5927\u6a21\u578b\u6682\u4e0d\u53ef\u7528\uff0c\u4ee5\u4e0a\u4e3a\u672c\u5730\u53ea\u8bfb\u5de5\u5177\u91c7\u96c6\u7ed3\u679c\u3002")',
        '    if degraded and summary_mode != "deterministic":\n'
        '        lines.append("")\n'
        '        lines.append("\u8bf4\u660e: \u5927\u6a21\u578b\u6682\u4e0d\u53ef\u7528\uff0c\u4ee5\u4e0a\u4e3a\u672c\u5730\u53ea\u8bfb\u5de5\u5177\u91c7\u96c6\u7ed3\u679c\u3002")',
    )

    old_tool = (
        '    degraded: bool = False,\n'
        '    parallel_result: dict[str, Any] | None = None,\n'
        ') -> str:\n'
        '    data = collect_tool_outputs(tool_trace, parallel_result, tool_out)\n'
        '    if intent in ("health", "monitor_status", "parallel_info", "processes", "general"):\n'
        '        text = format_health_summary(data, intent=intent, trace_id=trace_id, degraded=degraded)'
    )
    new_tool = (
        '    degraded: bool = False,\n'
        '    summary_mode: str = "auto",\n'
        '    parallel_result: dict[str, Any] | None = None,\n'
        ') -> str:\n'
        '    data = collect_tool_outputs(tool_trace, parallel_result, tool_out)\n'
        '    if intent in ("health", "monitor_status", "parallel_info", "processes", "general"):\n'
        '        text = format_health_summary(\n'
        '            data,\n'
        '            intent=intent,\n'
        '            trace_id=trace_id,\n'
        '            degraded=degraded,\n'
        '            summary_mode=summary_mode,\n'
        '        )'
    )
    text = text.replace(old_tool, new_tool)

    TARGET.write_text(text, encoding="utf-8")
    SRC.write_text(text, encoding="utf-8")
    print("patched ok", TARGET)


if __name__ == "__main__":
    main()

"""Security scanning engine — process and permission checks."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from security_agent import config
from security_agent.audit import log as audit
from security_agent.config import REPORTS_DIR, ensure_data_dirs
from security_agent.timeutil import TZ_LABEL, format_display, now_filename_ts, now_iso

_CMD_SPLIT = re.compile(r"\s+")


def _normalize_cmd_token(token: str) -> str:
    return token.strip("'\"`,;()[]{}").lower()


def _cmd_tokens(cmdline: str) -> list[str]:
    parts = re.split(r"[\s'\"`,;()=\[\]{}|&]+", cmdline.lower())
    return [_normalize_cmd_token(t) for t in parts if _normalize_cmd_token(t)]


def _is_log_read_context(tokens: list[str]) -> bool:
    """grep/cat 等查看日志时，高危词多为检索关键字，不视为执行."""
    if not tokens or tokens[0] not in config.HIGH_RISK_LOG_READ_PREFIXES:
        return False
    return any(t in config.HIGH_RISK_PROCESS_NAMES for t in tokens[1:])


def _match_high_risk_process(name: str, cmdline: str) -> str | None:
    cmd_lower = cmdline.lower()
    for frag in config.HIGH_RISK_SAFE_CMDLINE_FRAGMENTS:
        if frag in cmdline:
            return None

    base = (name or "").lower()
    tokens = _cmd_tokens(cmdline)
    if _is_log_read_context(tokens):
        return None

    if base not in config.HIGH_RISK_PROCESS_ALLOWLIST and base in config.HIGH_RISK_PROCESS_NAMES:
        return f"进程名匹配高危列表: {name}"
    for i, token in enumerate(tokens):
        if token not in config.HIGH_RISK_PROCESS_NAMES:
            continue
        if i > 0 and tokens[i - 1] == "help":
            continue
        return f"命令行包含高危工具: {token}"
    for pattern in config.HIGH_RISK_CMD_PATTERNS:
        if pattern in cmd_lower:
            return f"命令行匹配危险模式: {pattern}"
    return None


def match_high_risk_process(name: str, cmdline: str) -> str | None:
    """公开匹配入口，供演练校准与单测调用."""
    return _match_high_risk_process(name, cmdline)


def _check_sensitive_paths() -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for path_str in config.SENSITIVE_PATHS:
        path = Path(path_str)
        if not path.exists():
            continue
        try:
            writable = os.access(path, os.W_OK)
        except OSError:
            continue
        if not writable:
            continue
        if config.IS_WINDOWS:
            risks.append(
                {
                    "type": "权限异常",
                    "path": path_str,
                    "message": "敏感路径对当前用户可写",
                    "level": "高",
                }
            )
        else:
            try:
                is_root = os.geteuid() == 0
            except AttributeError:
                is_root = False
            if not is_root:
                risks.append(
                    {
                        "type": "权限异常",
                        "path": path_str,
                        "message": "敏感文件被非 root 用户赋予可写权限",
                        "level": "高",
                    }
                )
    return risks


def run_security_scan() -> dict[str, Any]:
    """Run full scan; returns structured result."""
    risks: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "username"]):
        try:
            info = proc.info
            name = info.get("name") or ""
            cmd_parts = info.get("cmdline") or []
            cmdline = " ".join(cmd_parts) if isinstance(cmd_parts, list) else str(cmd_parts)
            reason = _match_high_risk_process(name, cmdline)
            if reason:
                risks.append(
                    {
                        "type": "高危进程",
                        "pid": info.get("pid"),
                        "name": name,
                        "username": info.get("username"),
                        "cmdline": cmdline[:500],
                        "message": reason,
                        "level": "严重",
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    risks.extend(_check_sensitive_paths())
    result = {
        "scanned_at": now_iso(),
        "platform": config.platform_label(),
        "risks": risks,
        "risk_count": len(risks),
    }
    audit.append_audit("security_scan", {"risk_count": len(risks)})
    return result


def format_security_report(data: dict[str, Any] | str) -> str:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return "数据格式错误"
    risks = data.get("risks", [])
    lines = [
        "## 安全扫描摘要",
        f"- 平台: {data.get('platform', '—')}",
        f"- 扫描时间: {format_display(data.get('scanned_at'))} ({TZ_LABEL})",
        f"- 风险项数量: {len(risks)}",
    ]
    exposed = data.get("exposed_ports") or {}
    if exposed:
        if exposed.get("ok") is False:
            lines.append(f"- 端口检测: {exposed.get('message', '未完成')}")
        else:
            lines.append(
                f"- 全网卡监听: {exposed.get('listener_count', 0)} 个；"
                f"高危暴露: {exposed.get('risky_count', 0)} 个"
            )
    health = data.get("health") or {}
    if health:
        cpu = health.get("cpu_percent", health.get("cpu", "—"))
        mem = health.get("memory_percent", health.get("memory", "—"))
        lines.append(f"- 系统健康: CPU {cpu}% · 内存 {mem}%")
    if not risks:
        lines.extend(
            [
                "",
                "### 结论",
                "当前规则库（高危进程、敏感路径可写、高危端口暴露）下**未发现需处置项**.",
                "说明: 这不等于零风险；深度体检请用 Agent「综合体检」或工具 `run_full_security_check`.",
            ]
        )
        return "\n".join(lines)
    lines.extend(["", "### 风险明细"])
    for risk in risks[:30]:
        detail = risk.get("message") or risk.get("cmdline") or risk.get("path", "")
        pid = risk.get("pid")
        prefix = f"PID {pid} " if pid else ""
        lines.append(f"- [{risk.get('level', '?')}] {risk.get('type')}: {prefix}{detail}")
    if len(risks) > 30:
        lines.append(f"- … 另有 {len(risks) - 30} 项，见 HTML 报告或 JSON")
    return "\n".join(lines)


def is_elevated() -> bool:
    if config.IS_WINDOWS:
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def can_signal_process(pid: int) -> bool:
    """检测当前用户是否可向目标进程发信号."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    except OSError:
        return False


def block_process(pid: int, *, force: bool = False) -> dict[str, Any]:
    root_hint = f"sudo {config.PROJECT_ROOT}/boot_start.sh"
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        cmdline = " ".join(proc.cmdline()[:20])
        reason = _match_high_risk_process(name, cmdline)
        if not reason and not force:
            return {
                "ok": False,
                "needs_root": False,
                "message": f"PID {pid} 未在高危规则中，需勾选「强制拦截」或先扫描确认",
            }
        if not can_signal_process(pid):
            return {
                "ok": False,
                "needs_root": True,
                "message": f"权限不足：无法向 PID {pid} ({name}) 发送信号",
                "hint": (
                    f"终端执行: sudo kill -TERM {pid}\n"
                    f"或以 root 启动控制台: {root_hint}\n"
                    f"银河麒麟也可: pkexec kill -TERM {pid}"
                ),
            }
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            proc.kill()
        audit.append_audit(
            "block_process",
            {"pid": pid, "name": name, "forced": force},
            level="warning",
        )
        return {"ok": True, "needs_root": False, "message": f"已终止进程 PID {pid} ({name})"}
    except psutil.NoSuchProcess:
        return {"ok": False, "needs_root": False, "message": f"进程不存在: PID {pid}"}
    except psutil.AccessDenied:
        return {
            "ok": False,
            "needs_root": True,
            "message": f"权限不足，无法终止 PID {pid}（进程属主或其他用户）",
            "hint": f"sudo kill -TERM {pid}  或  {root_hint}",
        }


def list_processes(limit: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            cmd_parts = proc.cmdline()
            cmdline = " ".join(cmd_parts)[:200] if cmd_parts else ""
            reason = _match_high_risk_process(info.get("name") or "", cmdline)
            rows.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name"),
                    "username": info.get("username"),
                    "cpu_percent": info.get("cpu_percent"),
                    "memory_percent": info.get("memory_percent"),
                    "cmdline": cmdline,
                    "high_risk": reason is not None,
                    "risk_reason": reason,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if len(rows) >= limit:
            break
    return sorted(rows, key=lambda r: (not r["high_risk"], r.get("name") or ""))


def generate_html_report(scan_data: dict[str, Any], executive_summary: str = "") -> str:
    ensure_data_dirs()
    ts = now_filename_ts()
    path = REPORTS_DIR / f"security_report_{ts}.html"
    risks = scan_data.get("risks", [])
    rows = "".join(
        f"<tr><td>{r.get('level')}</td><td>{r.get('type')}</td>"
        f"<td>{r.get('pid', '')}</td><td>{r.get('name', r.get('path', ''))}</td>"
        f"<td>{r.get('message', r.get('cmdline', ''))}</td></tr>"
        for r in risks
    )

    # AI 执行摘要区块
    summary_section = ""
    if executive_summary:
        summary_section = f"""
<div class="ai-summary">
<h2>🤖 AI 执行摘要</h2>
<div class="summary-content">{executive_summary}</div>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="color-scheme" content="light">
<title>安全报告 {ts}</title>
<style>
body{{font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;margin:0;padding:24px 28px;background:#f5f7fa;color:#1e293b;}}
.wrap{{max-width:1100px;margin:0 auto;background:#fff;padding:24px 28px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08);}}
h1{{color:#0f172a;font-size:1.5rem;border-bottom:2px solid #1565c0;padding-bottom:8px;}}
h2{{color:#1e293b;font-size:1.2rem;margin-top:24px;}}
p{{color:#475569;}}
table{{border-collapse:collapse;width:100%;margin-top:16px;}}
th{{background:#1565c0;color:#fff;padding:10px 12px;text-align:left;}}
td{{border:1px solid #e2e8f0;padding:8px 12px;color:#334155;}}
tr:nth-child(even) td{{background:#f8fafc;}}
.empty{{color:#64748b;font-style:italic;}}
.ai-summary{{background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:16px;margin:16px 0;}}
.ai-summary h2{{color:#166534;margin-top:0;font-size:1.1rem;}}
.summary-content{{color:#1e293b;line-height:1.6;white-space:pre-wrap;}}
.model-badge{{display:inline-block;background:#22c55e;color:white;padding:2px 8px;border-radius:4px;font-size:0.75rem;margin-left:8px;}}
</style></head><body>
<div class="wrap">
<h1>安全运维扫描报告</h1>
<p>平台: {scan_data.get('platform')} | 时间: {format_display(scan_data.get('scanned_at'))} ({TZ_LABEL})</p>
<p>风险项: <strong>{len(risks)}</strong>{'<span class="model-badge">AI 增强</span>' if executive_summary else ''}</p>
{summary_section}
<table>
<tr><th>等级</th><th>类型</th><th>PID</th><th>对象</th><th>说明</th></tr>
{rows or '<tr><td colspan="5" class="empty">无风险</td></tr>'}
</table>
</div></body></html>"""
    path.write_text(html, encoding="utf-8")
    json_path = path.with_suffix(".json")
    json_path.write_text(json.dumps(scan_data, ensure_ascii=False, indent=2), encoding="utf-8")
    audit.append_audit("generate_report", {"path": str(path), "ai_summary": bool(executive_summary)})
    return str(path)

"""L2 sandbox envelope for write-cost tools."""

from __future__ import annotations
from typing import Any
from security_agent.pipeline.tool_taxonomy import tool_cost

_SANDBOX_AUDIT: list[dict[str, Any]] = []


def requires_sandbox(tool_name: str) -> bool:
    return tool_cost(tool_name) >= 1


def sandbox_preview(tool_name: str, arguments: dict[str, Any] | None, *, user_confirmed: bool = False) -> dict[str, Any]:
    args = arguments or {}
    if not requires_sandbox(tool_name):
        return {"verdict": "pass", "sandbox_required": False, "tool": tool_name, "envelope": None}

    envelope: dict[str, Any] = {"tool": tool_name, "sandbox_required": True, "layer": "L2", "method": "sandbox_executor"}

    if tool_name == "run_terminal_command" and args.get("command"):
        from security_agent.terminal.executor import run_terminal_sync
        result = run_terminal_sync(str(args["command"]), user_confirmed=user_confirmed or bool(args.get("confirmed")), force_sandbox=True)
        envelope["preview"] = {"ok": result.ok, "verdict": result.verdict, "message": result.message, "risk_level": result.risk_level, "trace_id": result.trace_id}
        verdict = "pass" if result.ok else "preview_fail"
        if result.verdict in ("DENY", "NEED_CONFIRM") and not result.ok:
            verdict = "confirm" if result.verdict == "NEED_CONFIRM" else "deny"
    else:
        envelope["preview"] = {"ok": True, "note": "write tool wrapped", "args_keys": list(args.keys())}
        verdict = "pass"

    _SANDBOX_AUDIT.append({"tool": tool_name, "verdict": verdict, "envelope": envelope})
    if len(_SANDBOX_AUDIT) > 200:
        _SANDBOX_AUDIT.pop(0)
    return {"verdict": verdict, "sandbox_required": True, "tool": tool_name, "envelope": envelope}


def recent_sandbox_audit(limit: int = 20) -> list[dict[str, Any]]:
    return list(reversed(_SANDBOX_AUDIT[-limit:]))
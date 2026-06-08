"""安全终端执行器 — 规则校验 + 最小权限代理 + 沙箱隔离.

集成 PrivilegeBroker: 根据风险等级自动降权到受限用户执行。
集成 SandboxExecutor: REVERSIBLE+ 写操作启用 OS 级隔离。
集成 TraceContext: 执行日志携带全局 trace_id。
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from typing import Any

from security_agent import config
from security_agent.audit import log as audit
from security_agent.audit.trace import TraceContext
from security_agent.rules.engine import RuleVerdict, check_terminal
from security_agent.safety_gate.risk import RiskLevel
from security_agent.security.redact import redact_command, redact_text
from security_agent.terminal.privilege import PrivilegeBroker, get_privilege_broker
from security_agent.terminal.sandbox import get_sandbox
from security_agent.timeutil import TZ_LABEL, format_display, now_iso


@dataclass
class TerminalResult:
    ok: bool
    command: str
    stdout: str
    stderr: str
    exit_code: int
    verdict: str
    message: str
    executed_at: str = ""
    executed_as_user: str = ""      # 实际执行的用户（最小权限）
    risk_level: str = ""            # 风险等级
    trace_id: str = ""              # 全链路追踪 ID
    auto_rollback_triggered: bool = False  # 是否触发了自动回滚

    def to_text(self) -> str:
        ts = format_display(self.executed_at) if self.executed_at else "—"
        parts = [
            f"执行时间 ({TZ_LABEL}): {ts}",
            f"命令: {redact_command(self.command)}",
            f"风险等级: {self.risk_level or '—'}",
            f"执行用户: {self.executed_as_user or '—'}",
            f"结果: {redact_text(self.message)}",
            f"退出码: {self.exit_code}",
        ]
        if self.stdout:
            parts.append(f"stdout:\n{redact_text(self.stdout[:4000])}")
        if self.stderr:
            parts.append(f"stderr:\n{redact_text(self.stderr[:2000])}")
        return "\n".join(parts)


def _maybe_auto_rollback(
    result: TerminalResult,
    snapshot_id: str | None,
    risk_level: RiskLevel | None,
) -> TerminalResult:
    """执行后自动回滚：如果命令失败且风险不可逆，自动恢复快照."""
    if snapshot_id is None or risk_level is None:
        return result
    if result.ok:
        return result
    if risk_level not in (RiskLevel.IRREVERSIBLE, RiskLevel.CRITICAL):
        return result

    from security_agent.safety_gate.snapshot import SnapshotManager

    mgr = SnapshotManager()
    restore = mgr.restore_snapshot(snapshot_id)
    audit.append_audit(
        "auto_rollback",
        {
            "trace_id": result.trace_id,
            "command": result.command[:200],
            "exit_code": result.exit_code,
            "snapshot_id": snapshot_id,
            "restored": restore.get("restored", []),
            "failed": restore.get("failed", []),
        },
        level="warning",
    )
    result.auto_rollback_triggered = True
    result.message = f"{result.message} | 自动回滚已触发(snap={snapshot_id})"
    return result


def _map_risk_level_to_mac(risk: RiskLevel) -> str:
    """RiskLevel → mac_checker 风险标签."""
    return {
        RiskLevel.CRITICAL: "DANGEROUS",
        RiskLevel.IRREVERSIBLE: "DANGEROUS",
        RiskLevel.REVERSIBLE: "MODERATE",
        RiskLevel.READONLY: "READONLY",
    }.get(risk, "MODERATE")


def _mac_pre_exec(command: str, risk_level: RiskLevel):
    """麒麟 MAC/SELinux 执行前检查；非麒麟环境优雅放行."""
    try:
        from security_agent.safety_gate.mac_checker import get_mac_checker

        return get_mac_checker(enforce=True).pre_exec_check(
            "terminal.exec",
            {"command": command},
            _map_risk_level_to_mac(risk_level),
        )
    except Exception:
        return None


def _map_risk_level_from_verdict(check) -> RiskLevel:
    """从规则引擎判定结果推导风险等级（兜底）."""
    if check.verdict == RuleVerdict.DENY:
        return RiskLevel.CRITICAL
    if check.verdict == RuleVerdict.NEED_CONFIRM:
        return RiskLevel.IRREVERSIBLE
    return RiskLevel.READONLY


def assess_terminal_risk(command: str) -> RiskLevel:
    """四级风险矩阵评估（与 SafetyGate 一致）."""
    from security_agent.safety_gate.risk import RiskAssessor

    return RiskAssessor().assess_terminal(command).level


def run_terminal_sync(
    command: str,
    *,
    timeout_sec: float = 30.0,
    cwd: str | None = None,
    user_confirmed: bool = False,
    risk_level: RiskLevel | None = None,
    force_sandbox: bool = False,
    snapshot_id: str | None = None,
) -> TerminalResult:
    """同步执行 shell 命令，经过规则校验 + 最小权限代理。

    执行流程:
        1. 规则引擎校验（check_terminal）
        2. 根据风险等级选择执行用户（PrivilegeBroker）
        3. 记录审计日志（携带 trace_id）

    Args:
        command: 要执行的 shell 命令
        timeout_sec: 超时秒数
        cwd: 工作目录
        user_confirmed: 用户是否已在 UI 中确认（REVERSIBLE+ 需要）
        risk_level: 外部传入的风险等级（来自 SafetyGate），优先于规则引擎自判
        force_sandbox: UI 沙箱模式 — 强制走 SandboxExecutor 并始终带回 risk_level

    Returns:
        TerminalResult
    """
    executed_at = now_iso()
    trace_id = TraceContext.current_trace_id()
    assessed_risk = risk_level or assess_terminal_risk(command)

    # 1. 规则引擎校验
    check = check_terminal(command, user_confirmed=user_confirmed)
    if check.verdict == RuleVerdict.DENY:
        return TerminalResult(
            ok=False,
            command=command,
            stdout="",
            stderr="",
            exit_code=-1,
            verdict=check.verdict.value,
            message=check.reason,
            executed_at=executed_at,
            trace_id=trace_id,
            risk_level=assessed_risk.name,
        )
    if check.verdict == RuleVerdict.NEED_CONFIRM and not user_confirmed:
        return TerminalResult(
            ok=False,
            command=command,
            stdout="",
            stderr="",
            exit_code=-1,
            verdict=check.verdict.value,
            message=f"{check.reason}（请在界面勾选确认后重试）",
            executed_at=executed_at,
            trace_id=trace_id,
            risk_level=assessed_risk.name,
        )

    # 2. 决定风险等级（评估器优先，规则引擎兜底）
    effective_risk = risk_level or assessed_risk
    if effective_risk == RiskLevel.READONLY and check.verdict != RuleVerdict.ALLOW:
        effective_risk = _map_risk_level_from_verdict(check)

    # 2.1 UI 沙箱模式：统一走沙箱执行器（只读/可逆/不可逆均带 risk_level）
    if force_sandbox:
        if effective_risk == RiskLevel.CRITICAL and not user_confirmed:
            return TerminalResult(
                ok=False,
                command=command,
                stdout="",
                stderr="",
                exit_code=-1,
                verdict=check.verdict.value,
                message="CRITICAL 命令需先在安全门禁审批或勾选确认",
                executed_at=executed_at,
                trace_id=trace_id,
                risk_level=effective_risk.name,
            )
        sandbox_result = get_sandbox().run(
            command,
            risk_level=effective_risk.name,
            timeout_sec=timeout_sec,
            cwd=cwd or str(config.PROJECT_ROOT),
        )
        audit.append_audit(
            "sandbox_exec",
            {
                "trace_id": trace_id,
                "command": command[:200],
                "exit_code": sandbox_result.exit_code,
                "risk_level": effective_risk.name,
                "forced_sandbox": True,
            },
            level="warning" if sandbox_result.exit_code != 0 else "info",
        )
        return _maybe_auto_rollback(
            TerminalResult(
                ok=sandbox_result.ok,
                command=command,
                stdout=sandbox_result.stdout,
                stderr=sandbox_result.stderr,
                exit_code=sandbox_result.exit_code,
                verdict=check.verdict.value,
                message="沙箱模式执行完成" if sandbox_result.ok else (sandbox_result.error or "沙箱执行失败"),
                executed_at=executed_at,
                executed_as_user=sandbox_result.executed_as_user,
                risk_level=effective_risk.name or sandbox_result.risk_level or assessed_risk.name,
                trace_id=trace_id,
            ),
            snapshot_id,
            effective_risk,
        )

    # 2.5 麒麟 MAC / SELinux 执行前钩子（L3 环境感知）
    mac_result = _mac_pre_exec(command, effective_risk)
    if mac_result is not None and not mac_result.allowed:
        audit.append_audit(
            "mac_check_deny",
            {
                "trace_id": trace_id,
                "command": command[:200],
                "reason": mac_result.reason,
                "platform": mac_result.platform,
            },
            level="warning",
        )
        return TerminalResult(
            ok=False,
            command=command,
            stdout="",
            stderr="",
            exit_code=-1,
            verdict=check.verdict.value,
            message=f"MAC 检查拒绝: {mac_result.reason}",
            executed_at=executed_at,
            trace_id=trace_id,
            risk_level=effective_risk.name,
        )
    if mac_result is not None:
        audit.append_audit(
            "mac_check_pass",
            {
                "trace_id": trace_id,
                "platform": mac_result.platform,
                "reason": mac_result.reason[:200],
            },
            level="info",
        )

    # 3. 写操作走沙箱（REVERSIBLE+），只读走 PrivilegeBroker
    if effective_risk in (RiskLevel.REVERSIBLE, RiskLevel.IRREVERSIBLE):
        sandbox_result = get_sandbox().run(
            command,
            risk_level=effective_risk.name,
            timeout_sec=timeout_sec,
            cwd=cwd or str(config.PROJECT_ROOT),
        )
        audit.append_audit(
            "sandbox_exec",
            {
                "trace_id": trace_id,
                "command": command[:200],
                "exit_code": sandbox_result.exit_code,
                "risk_level": effective_risk.name,
                "executed_as_user": sandbox_result.executed_as_user,
                "isolation": sandbox_result.isolation_method,
            },
            level="warning" if sandbox_result.exit_code != 0 else "info",
        )
        return _maybe_auto_rollback(
            TerminalResult(
                ok=sandbox_result.ok,
                command=command,
                stdout=sandbox_result.stdout,
                stderr=sandbox_result.stderr,
                exit_code=sandbox_result.exit_code,
                verdict=check.verdict.value,
                message="沙箱执行完成" if sandbox_result.ok else (sandbox_result.error or "沙箱执行失败"),
                executed_at=executed_at,
                executed_as_user=sandbox_result.executed_as_user,
                risk_level=effective_risk.name,
                trace_id=trace_id,
            ),
            snapshot_id,
            effective_risk,
        )

    broker = get_privilege_broker()
    priv_result = broker.execute(
        command,
        risk_level=effective_risk,
        user_confirmed=user_confirmed,
        timeout_sec=timeout_sec,
        cwd=cwd or str(config.PROJECT_ROOT),
    )

    audit.append_audit(
        "terminal_exec",
        {
            "trace_id": trace_id,
            "command": command[:200],
            "exit_code": priv_result.exit_code,
            "risk_level": effective_risk.name,
            "executed_as_user": priv_result.executed_as_user,
            "used_fallback": priv_result.used_fallback,
        },
        level="warning" if priv_result.exit_code != 0 else "info",
    )

    return _maybe_auto_rollback(
        TerminalResult(
            ok=priv_result.ok,
            command=command,
            stdout=priv_result.stdout,
            stderr=priv_result.stderr,
            exit_code=priv_result.exit_code,
            verdict=check.verdict.value,
            message="执行完成" if priv_result.ok else (priv_result.stderr or "执行失败"),
            executed_at=executed_at,
            executed_as_user=priv_result.executed_as_user,
            risk_level=effective_risk.name,
            trace_id=trace_id,
        ),
        snapshot_id,
        effective_risk,
    )


async def run_terminal(
    command: str,
    *,
    timeout_sec: float = 30.0,
    cwd: str | None = None,
    user_confirmed: bool = False,
    risk_level: RiskLevel | None = None,
    force_sandbox: bool = False,
    snapshot_id: str | None = None,
) -> TerminalResult:
    """异步封装：在线程池中运行同步执行器."""
    return await asyncio.to_thread(
        run_terminal_sync,
        command,
        timeout_sec=timeout_sec,
        cwd=cwd,
        user_confirmed=user_confirmed,
        risk_level=risk_level,
        force_sandbox=force_sandbox,
        snapshot_id=snapshot_id,
    )


# ---- 便捷：纯只读执行（跳过风险判断，直接以当前用户执行） ----

def run_readonly_sync(
    command: str,
    *,
    timeout_sec: float = 30.0,
    cwd: str | None = None,
) -> TerminalResult:
    """同步执行只读观测命令，自动以 READONLY 风险等级执行."""
    return run_terminal_sync(
        command,
        timeout_sec=timeout_sec,
        cwd=cwd,
        user_confirmed=True,
        risk_level=RiskLevel.READONLY,
    )


async def run_readonly(
    command: str,
    *,
    timeout_sec: float = 30.0,
    cwd: str | None = None,
) -> TerminalResult:
    """异步执行只读观测命令."""
    return await asyncio.to_thread(
        run_readonly_sync,
        command,
        timeout_sec=timeout_sec,
        cwd=cwd,
    )


# ---- 获取权限代理状态（供 UI/健康检查） ----

def get_privilege_status() -> dict[str, Any]:
    """获取当前权限代理引擎状态."""
    broker = get_privilege_broker()
    return broker.get_status()
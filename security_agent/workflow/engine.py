"""工作流引擎 — 自主任务的状态机与步骤执行."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from security_agent.audit import log as audit
from security_agent.rules.engine import ActionKind, RuleVerdict, check_action
from security_agent.timeutil import now_iso


class WorkflowState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_CONFIRM = "waiting_confirm"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    id: str
    kind: str  # tool | terminal | think
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | running | done | skipped | failed | need_confirm
    output: str = ""
    error: str = ""
    started_at: str = ""


@dataclass
class WorkflowRun:
    run_id: str
    goal: str
    state: WorkflowState = WorkflowState.IDLE
    steps: list[WorkflowStep] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=now_iso)
    user_confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "state": self.state.value,
            "steps": [
                {
                    "id": s.id,
                    "kind": s.kind,
                    "action": s.action,
                    "args": s.args,
                    "status": s.status,
                    "started_at": s.started_at,
                    "output": s.output[:500],
                    "error": s.error,
                }
                for s in self.steps
            ],
            "summary": self.summary,
            "trace": self.trace[-50:],
        }


StepExecutor = Callable[[WorkflowStep, WorkflowRun], Awaitable[str]]


class WorkflowEngine:
    def __init__(self, executor: StepExecutor):
        self._executor = executor
        self._runs: dict[str, WorkflowRun] = {}

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 10) -> list[WorkflowRun]:
        return list(self._runs.values())[-limit:]

    def create_run(self, goal: str) -> WorkflowRun:
        run = WorkflowRun(run_id=str(uuid.uuid4())[:8], goal=goal)
        self._runs[run.run_id] = run
        audit.append_audit("workflow_create", {"run_id": run.run_id, "goal": goal[:200]})
        return run

    def set_steps(self, run: WorkflowRun, steps: list[WorkflowStep]) -> None:
        run.steps = steps
        run.state = WorkflowState.RUNNING

    async def execute_run(
        self,
        run: WorkflowRun,
        *,
        max_steps: int = 12,
        stop_on_confirm: bool = True,
    ) -> WorkflowRun:
        run.state = WorkflowState.RUNNING
        executed = 0

        for step in run.steps:
            if step.status == "done":
                continue
            if executed >= max_steps:
                run.summary = "达到最大步骤数"
                run.state = WorkflowState.COMPLETED
                break

            step.status = "running"
            step.started_at = now_iso()
            run.trace.append(
                {
                    "event": "step_start",
                    "ts": step.started_at,
                    "step": step.id,
                    "action": step.action,
                }
            )

            # 规则门
            if step.kind == "terminal":
                check = check_action(
                    ActionKind.TERMINAL,
                    {"command": step.action},
                    user_confirmed=run.user_confirmed,
                )
            elif step.kind == "tool":
                check = check_action(
                    ActionKind.TOOL,
                    {"name": step.action, "args": step.args},
                    user_confirmed=run.user_confirmed,
                )
            else:
                check = None

            if check and check.verdict == RuleVerdict.DENY:
                step.status = "failed"
                step.error = check.reason
                run.state = WorkflowState.FAILED
                run.summary = f"规则拒绝: {check.reason}"
                run.trace.append({"event": "rule_deny", "reason": check.reason})
                return run

            if check and check.verdict == RuleVerdict.NEED_CONFIRM:
                step.status = "need_confirm"
                run.state = WorkflowState.WAITING_CONFIRM
                run.summary = f"等待确认: {check.reason}"
                run.trace.append({"event": "need_confirm", "step": step.id})
                if stop_on_confirm:
                    return run
                step.status = "skipped"
                continue

            try:
                output = await self._executor(step, run)
                step.output = output[:8000]
                step.status = "done"
                run.trace.append({"event": "step_done", "step": step.id, "preview": output[:300]})
            except Exception as exc:  # noqa: BLE001
                step.status = "failed"
                step.error = str(exc)
                run.state = WorkflowState.FAILED
                run.summary = str(exc)
                return run

            executed += 1

        if run.state == WorkflowState.RUNNING:
            run.state = WorkflowState.COMPLETED
            if not run.summary:
                run.summary = "工作流执行完成"

        audit.append_audit("workflow_finish", {"run_id": run.run_id, "state": run.state.value})
        return run

    def confirm_and_resume(self, run_id: str) -> WorkflowRun | None:
        run = self._runs.get(run_id)
        if not run:
            return None
        run.user_confirmed = True
        run.state = WorkflowState.RUNNING
        return run

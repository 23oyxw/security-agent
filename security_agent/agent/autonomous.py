"""自主 Agent — 规划 + 规则门控 + 工具/终端编排."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from security_agent import config
from security_agent.agent.rules import AUTOMATION_LEVEL, OPERATION_RULES
from security_agent.rules.engine import RuleVerdict, check_terminal
from security_agent.terminal.executor import run_terminal
from security_agent.tools.registry import call_tool_local
from security_agent.workflow.engine import WorkflowEngine, WorkflowRun, WorkflowState, WorkflowStep

PLANNER_PROMPT = """你是安全运维自主编排器。根据用户目标，输出 JSON 执行计划（只输出 JSON，无 markdown）。

格式:
{
  "steps": [
    {"kind": "tool", "action": "工具名", "args": {}},
    {"kind": "terminal", "action": "只读shell命令"},
    {"kind": "think", "action": "说明本步目的"}
  ],
  "summary_hint": "完成后如何向用户汇报"
}

可用工具名:
query_security_scan, query_security_scan_json, list_processes, get_process_detail,
generate_security_report, start_monitor, stop_monitor, get_monitor_events,
get_audit_log, get_system_health, list_network_connections, check_sensitive_paths,
run_full_security_check

终端仅允许观测类: ps, ss, df, free, uptime, grep, tail, journalctl status 等。
禁止: rm, kill(除非用户明确要求拦截), reboot, 管道下载执行。

规则:
""" + "\n".join(f"- {r}" for r in OPERATION_RULES)


def _autonomous_configured() -> bool:
    """自主任务 Agent 是否配置了独立 Key；未配置则回退到通用 LLM."""
    return bool(config.AUTONOMOUS_API_KEY)


class AutonomousAgent:
    def __init__(self, max_steps: int = 12):
        if not config.llm_configured() and not _autonomous_configured():
            raise ValueError("未配置 LLM API Key 或 AUTONOMOUS_API_KEY")
        api_key = config.AUTONOMOUS_API_KEY or config.LLM_API_KEY
        base_url = config.AUTONOMOUS_BASE_URL if config.AUTONOMOUS_API_KEY else config.LLM_BASE_URL
        self.model = (config.AUTONOMOUS_MODEL if config.AUTONOMOUS_API_KEY else config.LLM_MODEL).lower()
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.max_steps = max_steps
        self.engine = WorkflowEngine(executor=self._execute_step)
        self._last_run: WorkflowRun | None = None

    @property
    def last_run(self) -> WorkflowRun | None:
        return self._last_run

    async def _execute_step(self, step: WorkflowStep, run: WorkflowRun) -> str:
        if step.kind == "think":
            return step.action
        if step.kind == "tool":
            return await call_tool_local(step.action, step.args or {})
        if step.kind == "terminal":
            result = await run_terminal(
                step.action,
                user_confirmed=run.user_confirmed,
            )
            return result.to_text()
        return f"未知步骤类型: {step.kind}"

    def _parse_plan(self, raw: str) -> list[WorkflowStep]:
        text = raw.strip()
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            text = m.group(0)
        data = json.loads(text)
        steps: list[WorkflowStep] = []
        for i, item in enumerate(data.get("steps", [])[: self.max_steps]):
            steps.append(
                WorkflowStep(
                    id=f"s{i+1}",
                    kind=item.get("kind", "tool"),
                    action=item.get("action", ""),
                    args=item.get("args") or {},
                )
            )
        return steps

    def _default_plan(self, goal: str) -> list[WorkflowStep]:
        """无 LLM 或解析失败时的规则化默认计划."""
        g = goal.lower()
        steps: list[WorkflowStep] = []
        if any(k in g for k in ("扫描", "风险", "安全")):
            steps.append(WorkflowStep("s1", "tool", "run_full_security_check", {}))
            steps.append(WorkflowStep("s2", "terminal", "ps aux --sort=-%cpu | head -15", {}))
        elif any(k in g for k in ("进程", "process")):
            steps.append(WorkflowStep("s1", "tool", "list_processes", {"limit": 50}))
            steps.append(WorkflowStep("s2", "terminal", "ps aux | head -20", {}))
        elif any(k in g for k in ("监控",)):
            steps.append(WorkflowStep("s1", "tool", "start_monitor", {}))
            steps.append(WorkflowStep("s2", "tool", "get_monitor_events", {"limit": 20}))
        else:
            steps.append(WorkflowStep("s1", "tool", "query_security_scan", {}))
            steps.append(WorkflowStep("s2", "tool", "get_system_health", {}))
        return steps

    async def plan(self, goal: str) -> WorkflowRun:
        run = self.engine.create_run(goal)
        run.state = WorkflowState.PLANNING
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PLANNER_PROMPT},
                    {"role": "user", "content": f"目标: {goal}"},
                ],
                temperature=0.2,
            )
            raw = resp.choices[0].message.content or ""
            steps = self._parse_plan(raw)
            run.trace.append({"event": "plan_llm", "raw": raw[:500]})
        except Exception as exc:  # noqa: BLE001
            steps = self._default_plan(goal)
            run.trace.append({"event": "plan_fallback", "error": str(exc)})

        if not steps:
            steps = self._default_plan(goal)

        self.engine.set_steps(run, steps)
        self._last_run = run
        return run

    async def run(
        self,
        goal: str,
        *,
        user_confirmed: bool = False,
        resume_run_id: str | None = None,
    ) -> WorkflowRun:
        if resume_run_id:
            run = self.engine.get_run(resume_run_id)
            if not run:
                raise ValueError(f"未找到任务: {resume_run_id}")
            if user_confirmed:
                self.engine.confirm_and_resume(resume_run_id)
        else:
            run = await self.plan(goal)
            run.user_confirmed = user_confirmed

        # 从 waiting_confirm 的步骤继续
        if run.state == WorkflowState.WAITING_CONFIRM and user_confirmed:
            pending = [s for s in run.steps if s.status in ("need_confirm", "pending")]
            for step in pending:
                if step.status == "need_confirm":
                    step.status = "pending"

        run = await self.engine.execute_run(run, max_steps=self.max_steps)
        self._last_run = run

        # LLM 总结
        if run.state in (WorkflowState.COMPLETED, WorkflowState.WAITING_CONFIRM):
            run.summary = await self._summarize(run)

        return run

    async def _summarize(self, run: WorkflowRun) -> str:
        outputs = "\n".join(
            f"[{s.id}] {s.kind}/{s.action}: {s.output[:400] or s.error}"
            for s in run.steps
            if s.status in ("done", "failed", "need_confirm")
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "用简洁中文总结自主运维任务结果，先结论后要点。",
                    },
                    {
                        "role": "user",
                        "content": f"目标: {run.goal}\n状态: {run.state.value}\n\n步骤输出:\n{outputs[:6000]}",
                    },
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content or run.summary
        except Exception:
            return run.summary or "任务已执行，请查看步骤详情。"

    @staticmethod
    def automation_info() -> dict[str, Any]:
        return {
            **AUTOMATION_LEVEL,
            "terminal_allowlist": True,
            "autonomous_workflow": True,
        }

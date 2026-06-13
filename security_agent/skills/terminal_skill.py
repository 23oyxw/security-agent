"""终端 Skill — 封装终端命令执行、审计日志、风险演练能力."""

from __future__ import annotations

import json
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef


class TerminalSkill(SkillBase):
    """终端命令执行、审计日志查询、风险演练与检测校准."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="terminal",
            display_name="终端运维",
            description="白名单终端命令执行、审计日志查询、风险演练与检测校准",
            version="1.0.0",
            tags=("terminal", "audit", "demo"),
            requires_root=False,
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="run_terminal_command",
                description="在规则白名单内执行只读终端命令（观测类 ps/ss/df 等）",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell 命令"},
                        "confirmed": {"type": "boolean", "default": False},
                    },
                    "required": ["command"],
                },
                handler=self.run_terminal,
                auto_ok=True,
            ),
            ToolDef(
                name="get_audit_log",
                description="读取最近审计日志（JSON）",
                parameters={
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "default": 30}},
                    "required": [],
                },
                handler=self.audit_tail,
            ),
            ToolDef(
                name="run_risk_demo",
                description="运行本地风险演练场景（synthetic_mixed / live_decoy_process / terminal_boundary / full_drill / stop_decoys）",
                parameters={
                    "type": "object",
                    "properties": {
                        "scenario": {"type": "string", "description": "场景 ID", "default": "synthetic_mixed"},
                        "simulate_tool": {"type": "string", "description": "诱饵进程模拟的高危工具名", "default": "nmap"},
                    },
                    "required": [],
                },
                handler=self.risk_demo,
            ),
            ToolDef(
                name="test_terminal_boundaries",
                description="批量测试终端/工具规则边界（不执行危险命令）",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.terminal_boundaries,
            ),
            ToolDef(
                name="run_detection_calibration",
                description="运行 66 条日常/开发检测校准用例；category=all|daily_dev|attack_process|...|catalog",
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "用例分类，all 为全部，catalog 仅列出用例库",
                            "default": "all",
                        },
                    },
                    "required": [],
                },
                handler=self.detection_calibration,
            ),
            ToolDef(
                name="run_autonomous_mission",
                description="自主运维任务：自动规划并执行多步工具+终端（遵循规则引擎）",
                parameters={
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string", "description": "任务目标，自然语言"},
                        "confirmed": {"type": "boolean", "default": False},
                    },
                    "required": [],
                },
                handler=self.autonomous_mission,
                auto_ok=False,
            ),
        ]

    async def run_terminal(self, command: str, confirmed: bool = False) -> str:
        from security_agent.terminal.executor import run_terminal

        result = await run_terminal(command, user_confirmed=confirmed, force_sandbox=True)
        return result.to_text()

    async def audit_tail(self, limit: int = 30) -> str:
        from security_agent.audit.log import read_audit_tail

        return json.dumps(read_audit_tail(limit=limit), ensure_ascii=False)

    async def risk_demo(self, scenario: str = "synthetic_mixed", simulate_tool: str = "nmap") -> str:
        from security_agent.demo.service import get_demo_service

        svc = get_demo_service()
        if scenario == "stop_decoys":
            return json.dumps(svc.stop_decoys(), ensure_ascii=False, indent=2)
        out = svc.run_scenario(scenario, simulate_tool=simulate_tool)
        return json.dumps(out, ensure_ascii=False, indent=2, default=str)

    async def terminal_boundaries(self) -> str:
        from security_agent.demo.boundary import run_terminal_boundary_tests, summarize_boundary

        rows = run_terminal_boundary_tests()
        return json.dumps({"cases": rows, "summary": summarize_boundary(rows)}, ensure_ascii=False, indent=2)

    async def detection_calibration(self, category: str = "all") -> str:
        from security_agent.demo.service import get_demo_service

        svc = get_demo_service()
        if category == "catalog":
            return json.dumps(svc.get_fixture_catalog(), ensure_ascii=False, indent=2)
        return json.dumps(
            svc.run_fixture_calibration(category=None if category == "all" else category),
            ensure_ascii=False,
            indent=2,
        )

    async def autonomous_mission(self, goal: str = "", confirmed: bool = False) -> str:
        from security_agent.agent.autonomous import AutonomousAgent
        from security_agent.agent.orchestrator import resolve_autonomous_goal

        goal_text = resolve_autonomous_goal(goal or "")
        agent = AutonomousAgent()
        run = await agent.run(goal_text, user_confirmed=confirmed)
        return json.dumps(run.to_dict(), ensure_ascii=False, indent=2)


# Skill 自动发现入口
skill_instance = TerminalSkill()

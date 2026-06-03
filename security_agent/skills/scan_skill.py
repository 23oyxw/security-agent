"""安全扫描 Skill — 封装扫描与报告生成能力."""

from __future__ import annotations

import json
from typing import Any

from security_agent import config
from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.scanner import engine as scanner


class ScanSkill(SkillBase):
    """安全扫描与报告生成."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="scan",
            display_name="安全扫描",
            description="扫描系统安全状态，检测高危进程、端口暴露、可疑文件等，生成 HTML 报告",
            version="1.0.0",
            tags=("scanner", "report"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="query_security_scan",
                description="扫描系统安全状态，返回可读风险报告",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.scan,
            ),
            ToolDef(
                name="query_security_scan_json",
                description="扫描系统并返回 JSON 结构化结果",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.scan_json,
            ),
            ToolDef(
                name="generate_security_report",
                description="生成 HTML 安全扫描报告并返回文件路径，支持 Budget 模型生成 AI 摘要",
                parameters={
                    "type": "object",
                    "properties": {
                        "use_budget_model": {
                            "type": "boolean",
                            "description": "是否使用性价比更高的 Budget 模型生成报告摘要",
                            "default": True,
                        }
                    },
                    "required": [],
                },
                handler=self.generate_report,
            ),
        ]

    async def scan(self) -> str:
        data = scanner.run_security_scan()
        return scanner.format_security_report(data)

    async def scan_json(self) -> str:
        data = scanner.run_security_scan()
        return json.dumps(data, ensure_ascii=False)

    async def generate_report(self, use_budget_model: bool = True) -> str:
        data = scanner.run_security_scan()

        executive_summary = ""
        if use_budget_model and config.BUDGET_API_KEY:
            try:
                from security_agent.agent.budget import get_budget_agent
                budget_agent = get_budget_agent()
                executive_summary = budget_agent.generate_report_summary(data, format_type="executive")
            except Exception:
                executive_summary = ""

        path = scanner.generate_html_report(data, executive_summary=executive_summary)
        result = {
            "path": str(path),
            "risks_count": len(data.get("risks", [])),
            "ai_summary": executive_summary if executive_summary else None,
            "model_used": config.BUDGET_MODEL if (use_budget_model and executive_summary) else "default",
        }
        return json.dumps(result, ensure_ascii=False, indent=2)


# Skill 自动发现入口
skill_instance = ScanSkill()

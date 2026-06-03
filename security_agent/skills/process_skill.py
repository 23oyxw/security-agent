"""进程管理 Skill — 封装进程查看与拦截能力."""

from __future__ import annotations

import json
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.scanner import engine as scanner
from security_agent.tools import system_info


class ProcessSkill(SkillBase):
    """进程查看、详情查询与高危进程拦截."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="process",
            display_name="进程管理",
            description="列出系统进程、查询进程详情、拦截高危进程",
            version="1.0.0",
            tags=("process", "block", "security"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="list_processes",
                description="列出系统进程及是否命中高危规则",
                parameters={
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "default": 80}},
                    "required": [],
                },
                handler=self.list_processes,
            ),
            ToolDef(
                name="get_process_detail",
                description="查询单个 PID 的进程详情",
                parameters={
                    "type": "object",
                    "properties": {"pid": {"type": "integer"}},
                    "required": ["pid"],
                },
                handler=self.process_detail,
            ),
            ToolDef(
                name="block_high_risk_process",
                description="终止指定 PID 的进程；默认仅允许高危规则匹配的进程",
                parameters={
                    "type": "object",
                    "properties": {
                        "pid": {"type": "integer", "description": "进程 PID"},
                        "force": {"type": "boolean", "description": "强制终止（跳过高危校验）", "default": False},
                    },
                    "required": ["pid"],
                },
                handler=self.block_process,
                auto_ok=False,
            ),
        ]

    async def list_processes(self, limit: int = 80) -> str:
        rows = scanner.list_processes(limit=limit)
        return json.dumps(rows, ensure_ascii=False)

    async def process_detail(self, pid: int) -> str:
        return json.dumps(system_info.get_process_detail(pid), ensure_ascii=False)

    async def block_process(self, pid: int, force: bool = False) -> str:
        result = scanner.block_process(pid, force=force)
        return result["message"]


# Skill 自动发现入口
skill_instance = ProcessSkill()

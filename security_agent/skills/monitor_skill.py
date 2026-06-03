"""监控 Skill — 封装后台进程监控能力."""

from __future__ import annotations

import json
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.monitor import get_monitor_service


class MonitorSkill(SkillBase):
    """后台进程与敏感路径监控的启停与事件查询."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="monitor",
            display_name="实时监控",
            description="启动/停止后台监控，查询监控事件",
            version="1.0.0",
            tags=("monitor", "realtime"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="start_monitor",
                description="启动后台进程与敏感路径监控",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.start,
            ),
            ToolDef(
                name="stop_monitor",
                description="停止后台监控",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.stop,
            ),
            ToolDef(
                name="get_monitor_events",
                description="获取监控事件列表（JSON）",
                parameters={
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "default": 50}},
                    "required": [],
                },
                handler=self.get_events,
            ),
        ]

    async def start(self) -> str:
        return get_monitor_service().start()

    async def stop(self) -> str:
        return get_monitor_service().stop()

    async def get_events(self, limit: int = 50) -> str:
        events = get_monitor_service().get_events(limit=limit)
        return json.dumps(events, ensure_ascii=False)


# Skill 自动发现入口
skill_instance = MonitorSkill()

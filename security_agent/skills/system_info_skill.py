"""系统信息 Skill — 封装系统健康检查与网络连接能力."""

from __future__ import annotations

import json
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.tools import system_info


class SystemInfoSkill(SkillBase):
    """系统健康、网络连接、敏感路径与综合体检."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="system_info",
            display_name="系统信息",
            description="获取系统健康指标、网络连接、敏感路径检查与综合安全体检",
            version="1.0.0",
            tags=("system", "health", "network"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="get_system_health",
                description="获取 CPU/内存/磁盘/平台/是否 root 等系统健康信息",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.health,
            ),
            ToolDef(
                name="list_network_connections",
                description="列出网络连接（可能需 root 才能看全）",
                parameters={
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "default": 50}},
                    "required": [],
                },
                handler=self.network_connections,
            ),
            ToolDef(
                name="check_sensitive_paths",
                description="检查配置的敏感路径是否存在及可写",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.sensitive_paths,
            ),
            ToolDef(
                name="check_exposed_ports",
                description="检测 0.0.0.0 监听的高危端口（数据库/远控/调试口等）",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.exposed_ports,
            ),
            ToolDef(
                name="run_full_security_check",
                description="一键综合体检：扫描+系统健康+敏感路径+连接采样",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.full_check,
            ),
        ]

    async def health(self) -> str:
        return json.dumps(system_info.get_system_health(), ensure_ascii=False)

    async def network_connections(self, limit: int = 50) -> str:
        return json.dumps(system_info.list_network_connections(limit=limit), ensure_ascii=False)

    async def sensitive_paths(self) -> str:
        return json.dumps(system_info.check_sensitive_paths(), ensure_ascii=False)

    async def exposed_ports(self) -> str:
        return json.dumps(system_info.check_exposed_ports(), ensure_ascii=False, indent=2)

    async def full_check(self) -> str:
        return json.dumps(system_info.full_security_check(), ensure_ascii=False, default=str)


# Skill 自动发现入口
skill_instance = SystemInfoSkill()

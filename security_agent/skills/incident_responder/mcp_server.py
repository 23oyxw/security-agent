"""IncidentResponder MCP Server — 独立运行的故障响应服务.

使用方式:
    python -m security_agent.skills.incident_responder.mcp_server
    python -m security_agent.skills.incident_responder.mcp_server --transport http --port 8085
    python -m security_agent.skills.incident_responder.mcp_server --info
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from security_agent.skills.mcp_base import MCPSkillServer, MCPTool
from security_agent.skills.incident_responder.skill import IncidentResponderSkill


class IncidentResponderMCPServer(MCPSkillServer):
    """故障响应 MCP 服务."""

    name = "incident_responder"
    display_name = "故障响应"
    description = "根因分析决策树、自愈脚本、处置流程编排"
    version = "1.0.0"
    port = 8085

    def __init__(self):
        super().__init__()
        self._skill = IncidentResponderSkill()

    def get_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="incident_diagnose",
                description="故障诊断：针对CPU/磁盘/内存/服务问题执行根因分析",
                parameters={
                    "type": "object",
                    "properties": {
                        "incident_type": {
                            "type": "string",
                            "description": "故障类型: high_cpu|disk_full|high_memory|service_down|unknown",
                            "enum": ["high_cpu", "disk_full", "high_memory", "service_down", "unknown"],
                        }
                    },
                    "required": ["incident_type"],
                },
                handler=self._tool_diagnose,
            ),
            MCPTool(
                name="incident_self_heal",
                description="【写入操作】执行自愈脚本：清理临时文件、日志轮转等（仅限低风险脚本）",
                parameters={
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "自愈脚本ID: clear_tmp(清理临时文件) / rotate_logs(日志轮转) / clear_cache(包缓存)",
                            "enum": ["clear_tmp", "rotate_logs", "clear_cache"],
                        }
                    },
                    "required": ["script_id"],
                },
                handler=self._tool_self_heal,
                requires_confirmation=True,
            ),
            MCPTool(
                name="incident_list_scripts",
                description="列出所有可用的自愈脚本",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_list_scripts,
            ),
            MCPTool(
                name="incident_response_plan",
                description="生成故障响应计划（含处置步骤、预估时间、风险等级）",
                parameters={
                    "type": "object",
                    "properties": {
                        "incident_type": {
                            "type": "string",
                            "description": "故障类型",
                        }
                    },
                    "required": ["incident_type"],
                },
                handler=self._tool_response_plan,
            ),
        ]

    async def _tool_diagnose(self, incident_type: str, **kwargs) -> str:
        result = self._skill.auto_diagnose(incident_type)
        return json.dumps(result.to_dict() if hasattr(result, "to_dict") else result, ensure_ascii=False, indent=2)

    async def _tool_self_heal(self, script_id: str, **kwargs) -> str:
        result = self._skill.execute_self_heal(script_id)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_list_scripts(self, **kwargs) -> str:
        from security_agent.skills.incident_responder.skill import SELF_HEAL_SCRIPTS
        result = {
            "scripts": [
                {
                    "id": sid,
                    "name": script["name"],
                    "description": script["description"],
                    "auto_ok": script["auto_ok"],
                    "risk_level": script["risk_level"],
                }
                for sid, script in SELF_HEAL_SCRIPTS.items()
            ]
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_response_plan(self, incident_type: str, **kwargs) -> str:
        result = self._skill.generate_response_plan(incident_type)
        return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    IncidentResponderMCPServer.main()

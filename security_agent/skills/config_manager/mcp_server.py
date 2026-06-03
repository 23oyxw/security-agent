"""ConfigManager MCP Server — 独立运行的配置管理服务.

使用方式:
    python -m security_agent.skills.config_manager.mcp_server
    python -m security_agent.skills.config_manager.mcp_server --transport http --port 8083
    python -m security_agent.skills.config_manager.mcp_server --info

工具列表:
    - config_snapshot: 生成配置文件快照
    - config_diff: 对比配置差异
    - config_history: 查看变更历史
    - config_audit: 审计配置状态
    - config_add_watch: 添加监控文件
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from security_agent.skills.mcp_base import MCPSkillServer, MCPTool
from security_agent.skills.config_manager.skill import ConfigManagerSkill


class ConfigManagerMCPServer(MCPSkillServer):
    """配置管理 MCP 服务."""

    name = "config_manager"
    display_name = "配置管理"
    description = "关键配置文件快照、变更检测、diff展示、版本追踪"
    version = "1.0.0"
    port = 8083

    def __init__(self):
        super().__init__()
        self._skill = ConfigManagerSkill()

    def get_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="config_snapshot",
                description="对关键配置文件生成快照（哈希+内容），用于变更检测",
                parameters={
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "string",
                            "description": "逗号分隔的文件路径（留空=默认12个关键配置）",
                        }
                    },
                    "required": [],
                },
                handler=self._tool_snapshot,
            ),
            MCPTool(
                name="config_diff",
                description="对比当前配置与最近一次快照的差异（类git diff格式）",
                parameters={
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "指定文件路径（留空=检查所有受管文件）",
                        }
                    },
                    "required": [],
                },
                handler=self._tool_diff,
            ),
            MCPTool(
                name="config_history",
                description="查看配置文件的变更历史（最近N次快照）",
                parameters={
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "文件路径，如 /etc/ssh/sshd_config"},
                        "limit": {"type": "integer", "description": "返回条数", "default": 10},
                    },
                    "required": ["file"],
                },
                handler=self._tool_history,
            ),
            MCPTool(
                name="config_audit",
                description="审计所有受管配置文件的状态：存在性、权限、最后修改时间",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_audit,
            ),
            MCPTool(
                name="config_add_watch",
                description="添加一个配置文件到监控列表（支持自定义监控）",
                parameters={
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "文件路径"},
                        "category": {"type": "string", "description": "分类标签", "default": "自定义"},
                    },
                    "required": ["file"],
                },
                handler=self._tool_add_watch,
            ),
        ]

    async def _tool_snapshot(self, files: str = "", **kwargs) -> str:
        file_list = files.split(",") if files else []
        result = self._skill.take_snapshot(file_list)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_diff(self, file: str = "", **kwargs) -> str:
        result = self._skill.diff_config(file)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_history(self, file: str, limit: int = 10, **kwargs) -> str:
        result = self._skill.get_history(file, limit)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_audit(self, **kwargs) -> str:
        result = self._skill.audit_configs()
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_add_watch(self, file: str, category: str = "自定义", **kwargs) -> str:
        result = self._skill.add_managed_config(file, category)
        return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    ConfigManagerMCPServer.main()

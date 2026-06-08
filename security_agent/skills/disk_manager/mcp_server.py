"""DiskManager MCP Server — 磁盘管理 MCP 服务.

工具列表:
    - disk_usage: 分区使用情况
    - disk_io_stats: IO 统计
    - disk_large_files: 大文件扫描
    - disk_cleanable: 可清理分析
    - disk_backup: 文件备份
    - disk_list_backups: 备份列表
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from security_agent.skills.mcp_base import MCPSkillServer, MCPTool
from security_agent.skills.disk_manager.skill import DiskManagerSkill


class DiskManagerMCPServer(MCPSkillServer):
    name = "disk_manager"
    display_name = "磁盘管理"
    description = "磁盘空间分析、IO 监控、大文件扫描、备份恢复"
    version = "1.0.0"
    port = 8084

    def __init__(self):
        super().__init__()
        self._skill = DiskManagerSkill()

    def get_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="disk_usage",
                description="获取所有分区的磁盘使用情况，标注超过 85% 的告警分区",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_disk_usage,
                requires_confirmation=False,
            ),
            MCPTool(
                name="disk_io_stats",
                description="获取磁盘 IO 统计：读取/写入量、IO 队列深度（iostat 或 /proc/diskstats）",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_io_stats,
                requires_confirmation=False,
            ),
            MCPTool(
                name="disk_large_files",
                description="扫描指定目录下的最大文件（降序排列 Top20），用于磁盘空间排查",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "扫描起始目录",
                            "default": "/",
                        },
                        "min_size_mb": {
                            "type": "integer",
                            "description": "最小文件大小（MB）",
                            "default": 100,
                            "minimum": 1,
                        },
                    },
                    "required": [],
                },
                handler=self._tool_large_files,
                requires_confirmation=False,
            ),
            MCPTool(
                name="disk_cleanable",
                description="分析可清理目录：/tmp、/var/tmp、~/.cache 的文件数量与总大小",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_cleanable,
                requires_confirmation=False,
            ),
            MCPTool(
                name="disk_backup",
                description="备份指定文件到 data/backups/，带时间戳防止覆盖",
                parameters={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "要备份的源文件路径",
                        },
                    },
                    "required": ["source"],
                },
                handler=self._tool_backup,
                requires_confirmation=True,
            ),
            MCPTool(
                name="disk_list_backups",
                description="列出已有备份文件",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_list_backups,
                requires_confirmation=False,
            ),
        ]

    async def _tool_disk_usage(self, **kwargs) -> str:
        return json.dumps(self._skill.disk_usage(), ensure_ascii=False, indent=2)

    async def _tool_io_stats(self, **kwargs) -> str:
        return json.dumps(self._skill.io_stats(), ensure_ascii=False, indent=2)

    async def _tool_large_files(self, path: str = "/", min_size_mb: int = 100, **kwargs) -> str:
        return json.dumps(self._skill.find_large_files(path, min_size_mb), ensure_ascii=False, indent=2)

    async def _tool_cleanable(self, **kwargs) -> str:
        return json.dumps(self._skill.analyze_cleanable(), ensure_ascii=False, indent=2)

    async def _tool_backup(self, source: str, **kwargs) -> str:
        return json.dumps(self._skill.backup_file(source), ensure_ascii=False, indent=2)

    async def _tool_list_backups(self, **kwargs) -> str:
        return json.dumps(self._skill.list_backups(), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    DiskManagerMCPServer.main()

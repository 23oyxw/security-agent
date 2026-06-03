"""LogAnalyzer MCP Server — 独立运行的日志分析服务.

使用方式:
    python -m security_agent.skills.log_analyzer.mcp_server
    python -m security_agent.skills.log_analyzer.mcp_server --transport http --port 8082
    python -m security_agent.skills.log_analyzer.mcp_server --info
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from security_agent.skills.mcp_base import MCPSkillServer, MCPTool
from security_agent.skills.log_analyzer.skill import LogAnalyzerSkill


class LogAnalyzerMCPServer(MCPSkillServer):
    """日志分析 MCP 服务."""
    
    name = "log_analyzer"
    display_name = "日志分析"
    description = "多源日志采集、模式识别、异常检测、告警关联"
    version = "1.0.0"
    port = 8082
    
    def __init__(self):
        super().__init__()
        self._skill = LogAnalyzerSkill()
    
    def get_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="log_scan",
                description="扫描所有日志源，检测异常模式（暴力破解、服务崩溃、磁盘错误等10种）",
                parameters={
                    "type": "object",
                    "properties": {
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "指定日志文件路径列表（默认自动发现）",
                        }
                    },
                    "required": [],
                },
                handler=self._tool_scan,
            ),
            MCPTool(
                name="log_tail",
                description="实时跟踪日志尾部（类似 tail -f），返回最近 N 行",
                parameters={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "日志文件路径（如 /var/log/auth.log）",
                        },
                        "lines": {
                            "type": "integer",
                            "description": "读取行数",
                            "default": 50,
                        }
                    },
                    "required": ["source"],
                },
                handler=self._tool_tail,
            ),
            MCPTool(
                name="log_search",
                description="关键词搜索日志",
                parameters={
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "搜索关键词",
                        },
                        "source": {
                            "type": "string",
                            "description": "日志文件路径（默认全部）",
                            "default": "",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最大返回条数",
                            "default": 20,
                        }
                    },
                    "required": ["keyword"],
                },
                handler=self._tool_search,
            ),
            MCPTool(
                name="log_patterns",
                description="获取支持的异常模式列表（10种安全相关模式）",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_patterns,
            ),
            MCPTool(
                name="log_recent_matches",
                description="获取最近的异常匹配记录",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "返回条数",
                            "default": 20,
                        }
                    },
                    "required": [],
                },
                handler=self._tool_recent_matches,
            ),
            MCPTool(
                name="log_incremental_scan",
                description="增量扫描：只扫描上次扫描后的新内容",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_incremental_scan,
            ),
        ]
    
    async def _tool_scan(self, sources: list[str] | None = None, **kwargs) -> str:
        result = self._skill.scan_sources(sources)
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    async def _tool_tail(self, source: str, lines: int = 50, **kwargs) -> str:
        result = self._skill.tail_log(source, lines)
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    async def _tool_search(self, keyword: str, source: str = "", limit: int = 20, **kwargs) -> str:
        result = self._skill.search_logs(keyword, source, limit)
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    async def _tool_patterns(self, **kwargs) -> str:
        result = {
            "patterns": list(self._skill._patterns.keys()),
            "total": len(self._skill._patterns),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    async def _tool_recent_matches(self, limit: int = 20, **kwargs) -> str:
        result = self._skill.get_recent_matches(limit)
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    async def _tool_incremental_scan(self, **kwargs) -> str:
        result = self._skill.incremental_scan()
        return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    LogAnalyzerMCPServer.main()

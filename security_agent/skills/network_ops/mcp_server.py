"""NetworkOps MCP Server — 网络运维 MCP 服务.

工具列表:
    - net_scan_ports: 端口扫描
    - net_analyze_connections: 连接分析
    - net_firewall_status: 防火墙状态检查
    - net_firewall_rules: iptables 规则列表
    - net_check_dns: DNS 解析检查
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from security_agent.skills.mcp_base import MCPSkillServer, MCPTool
from security_agent.skills.network_ops.skill import NetworkOpsSkill


class NetworkOpsMCPServer(MCPSkillServer):
    name = "network_ops"
    display_name = "网络运维"
    description = "端口扫描、连接分析、防火墙管理、DNS 检查"
    version = "1.0.0"
    port = 8083

    def __init__(self):
        super().__init__()
        self._skill = NetworkOpsSkill()

    def get_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="net_scan_ports",
                description="扫描本地监听端口：TCP/UDP 端口列表、进程信息、暴露端口检测（0.0.0.0 绑定）",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "目标主机（默认 127.0.0.1）",
                            "default": "127.0.0.1",
                        },
                    },
                    "required": [],
                },
                handler=self._tool_scan_ports,
                requires_confirmation=False,
            ),
            MCPTool(
                name="net_analyze_connections",
                description="分析当前网络连接：状态分布、ESTABLISHED 比例、高频外部连接 IP、可疑连接（>=50 连接/IP）",
                parameters={
                    "type": "object",
                    "properties": {
                        "min_count": {
                            "type": "integer",
                            "description": "高频连接阈值（默认10）",
                            "default": 10,
                        },
                    },
                    "required": [],
                },
                handler=self._tool_analyze_connections,
                requires_confirmation=False,
            ),
            MCPTool(
                name="net_firewall_status",
                description="检查防火墙状态：iptables 默认策略 + ufw + firewalld 活动状态",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_firewall_status,
                requires_confirmation=False,
            ),
            MCPTool(
                name="net_firewall_rules",
                description="列出 iptables 防火墙规则（只读）",
                parameters={
                    "type": "object",
                    "properties": {
                        "table": {
                            "type": "string",
                            "description": "iptables 表名（filter/nat/mangle）",
                            "default": "filter",
                            "enum": ["filter", "nat", "mangle"],
                        },
                    },
                    "required": [],
                },
                handler=self._tool_firewall_rules,
                requires_confirmation=False,
            ),
            MCPTool(
                name="net_check_dns",
                description="检查域名 DNS 解析",
                parameters={
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "要检查的域名",
                        },
                        "nameserver": {
                            "type": "string",
                            "description": "指定 DNS 服务器（可选）",
                            "default": "",
                        },
                    },
                    "required": ["domain"],
                },
                handler=self._tool_check_dns,
                requires_confirmation=False,
            ),
        ]

    async def _tool_scan_ports(self, host: str = "127.0.0.1", **kwargs) -> str:
        return json.dumps(self._skill.scan_ports(host), ensure_ascii=False, indent=2)

    async def _tool_analyze_connections(self, min_count: int = 10, **kwargs) -> str:
        return json.dumps(self._skill.analyze_connections(min_count), ensure_ascii=False, indent=2)

    async def _tool_firewall_status(self, **kwargs) -> str:
        return json.dumps(self._skill.check_firewall_status(), ensure_ascii=False, indent=2)

    async def _tool_firewall_rules(self, table: str = "filter", **kwargs) -> str:
        return json.dumps(self._skill.list_firewall_rules(table), ensure_ascii=False, indent=2)

    async def _tool_check_dns(self, domain: str, nameserver: str = "", **kwargs) -> str:
        return json.dumps(self._skill.check_dns(domain, nameserver), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    NetworkOpsMCPServer.main()

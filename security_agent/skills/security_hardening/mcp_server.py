"""SecurityHardening MCP Server — 独立运行的安全加固服务.

使用方式:
    python -m security_agent.skills.security_hardening.mcp_server
    python -m security_agent.skills.security_hardening.mcp_server --transport http --port 8084
    python -m security_agent.skills.security_hardening.mcp_server --info
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from security_agent.skills.mcp_base import MCPSkillServer, MCPTool
from security_agent.skills.security_hardening.skill import SecurityHardeningSkill


class SecurityHardeningMCPServer(MCPSkillServer):
    """安全加固 MCP 服务."""

    name = "security_hardening"
    display_name = "安全加固"
    description = "SSH审计、防火墙审查、漏洞扫描、CIS基线合规检查"
    version = "1.0.0"
    port = 8084

    def __init__(self):
        super().__init__()
        self._skill = SecurityHardeningSkill()

    def get_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="hardening_ssh_audit",
                description="SSH配置安全审计：检查密码认证、Root登录、端口、协议版本",
                parameters={
                    "type": "object",
                    "properties": {
                        "config_path": {
                            "type": "string",
                            "description": "SSH配置文件路径（默认/etc/ssh/sshd_config）",
                            "default": "/etc/ssh/sshd_config",
                        }
                    },
                    "required": [],
                },
                handler=self._tool_ssh_audit,
            ),
            MCPTool(
                name="hardening_firewall_audit",
                description="防火墙规则审计：检查默认策略、开放端口、IP转发",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_firewall_audit,
            ),
            MCPTool(
                name="hardening_vulnerability_scan",
                description="常见漏洞扫描：检查弱密码、SUID文件、World-writable文件",
                parameters={
                    "type": "object",
                    "properties": {
                        "quick": {
                            "type": "boolean",
                            "description": "快速扫描（只查关键路径）",
                            "default": True,
                        }
                    },
                    "required": [],
                },
                handler=self._tool_vuln_scan,
            ),
            MCPTool(
                name="hardening_baseline_check",
                description="CIS基线合规检查：系统加固建议与评分",
                parameters={
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "string",
                            "description": "检查级别: L1(基本) | L2(高级)",
                            "enum": ["L1", "L2"],
                            "default": "L1",
                        }
                    },
                    "required": [],
                },
                handler=self._tool_baseline_check,
            ),
            MCPTool(
                name="hardening_full_scan",
                description="执行完整安全扫描（SSH+防火墙+漏洞+基线）",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_full_scan,
            ),
        ]

    async def _tool_ssh_audit(self, config_path: str = "/etc/ssh/sshd_config", **kwargs) -> str:
        result = self._skill.audit_ssh(config_path)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_firewall_audit(self, **kwargs) -> str:
        result = self._skill.audit_firewall()
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_vuln_scan(self, quick: bool = True, **kwargs) -> str:
        result = self._skill.scan_vulnerabilities(quick)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_baseline_check(self, level: str = "L1", **kwargs) -> str:
        result = self._skill.check_baseline(level)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_full_scan(self, **kwargs) -> str:
        result = self._skill.full_scan()
        return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    SecurityHardeningMCPServer.main()

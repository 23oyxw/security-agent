"""四级风险判定引擎 — 只读/可逆/不可逆/关键 四级风险矩阵.

赛题要求：
  - 只读 (READONLY)    → 自动放行
  - 可逆 (REVERSIBLE)  → 需用户确认
  - 不可逆 (IRREVERSIBLE) → 需用户明确授权 + 自动备份
  - 关键 (CRITICAL)    → 触发人工审批流程
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class RiskLevel(IntEnum):
    """四级风险等级（数值越大风险越高）."""
    READONLY = 0        # 只读观测，自动放行
    REVERSIBLE = 1      # 可逆操作，需确认
    IRREVERSIBLE = 2    # 不可逆操作，需明确授权 + 自动备份
    CRITICAL = 3        # 关键操作，触发人工审批

    def label(self) -> str:
        return {
            RiskLevel.READONLY: "只读",
            RiskLevel.REVERSIBLE: "可逆",
            RiskLevel.IRREVERSIBLE: "不可逆",
            RiskLevel.CRITICAL: "关键",
        }[self]

    def needs_confirmation(self) -> bool:
        return self >= RiskLevel.REVERSIBLE

    def needs_approval(self) -> bool:
        return self >= RiskLevel.IRREVERSIBLE

    def needs_backup(self) -> bool:
        return self >= RiskLevel.IRREVERSIBLE

    def needs_escalation(self) -> bool:
        return self == RiskLevel.CRITICAL


@dataclass
class RiskAssessment:
    """风险评估结果."""
    level: RiskLevel
    reason: str
    rule_id: str = ""
    suggested_action: str = ""
    requires_backup: bool = False
    requires_escalation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.name,
            "level_label": self.level.label(),
            "reason": self.reason,
            "rule_id": self.rule_id,
            "suggested_action": self.suggested_action,
            "requires_backup": self.requires_backup,
            "requires_escalation": self.requires_escalation,
            "metadata": self.metadata,
        }


# ---- 高危命令模式（直接判定为 CRITICAL） ----
CRITICAL_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\s+/[^ ]*", "根目录递归删除"),
    (r"\bmkfs\b", "格式化文件系统"),
    (r"\bdd\s+if=\s*/dev/[^ ]+\s+of=\s*/dev/[^ ]+", "硬盘覆写"),
    (r"\bdd\s+if=\s*/dev/zero\b", "设备清零"),
    (r"shutdown\s+-[rh now]+", "系统关机/重启"),
    (r"reboot", "系统重启"),
    (r"init\s+0", "关机"),
    (r"iptables\s+-F", "清空防火墙规则"),
    (r">\s*/dev/[^ ]+", "清空设备"),
    (r":\(\)\s*\{", "Fork炸弹"),
    (r"chmod\s+777\s+/", "根目录777"),
    (r"passwd\s+(root|admin)", "修改系统账号密码"),
    (r"\buserdel\s+", "删除用户"),
]

# ---- 不可逆操作模式（判定为 IRREVERSIBLE） ----
IRREVERSIBLE_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\b", "强制递归删除"),
    (r"\bsudo\s+(rm|chmod|chown|userdel|useradd|groupadd|usermod|passwd)\b", "sudo权限变更"),
    (r"\bchown\s+", "修改文件所有者"),
    (r"\bchmod\s+[0-7]{3,4}\b", "修改文件权限"),
    (r">\s*/etc/", "覆写系统配置"),
    (r"\btee\s+/etc/", "写入系统配置"),
    (r"systemctl\s+(restart|stop|disable|mask)\s+", "停止/禁用系统服务"),
    (r"apt\s+(remove|purge|autoremove)\b", "卸载软件包"),
    (r"pip\s+uninstall\b", "卸载Python包"),
    (r"docker\s+(rm|rmi|stop)\b", "Docker删除操作"),
]

# ---- 可逆操作模式（判定为 REVERSIBLE） ----
REVERSIBLE_PATTERNS: list[tuple[str, str]] = [
    (r"\bkill\s+", "终止进程"),
    (r"\bpkill\s+", "批量终止进程"),
    (r"\bsystemctl\s+reload\b", "重载服务配置"),
    (r"\bapt\s+install\b", "安装软件包"),
    (r"\bpip\s+install\b", "安装Python包"),
    (r"\bdocker\s+start\b", "启动容器"),
    (r"\bdocker\s+stop\b", "停止容器"),
    (r"iptables\s+-[AIR]\b", "修改防火墙规则"),
    (r"\bsed\s+-i\b", "原地修改文件"),
    (r"\bcurl\s+.*-o\b", "下载文件"),
    (r"\bwget\s+.*-O\b", "下载文件"),
    (r"\bmkdir\b", "创建目录"),
    (r"\btouch\b", "创建文件"),
    (r"\bmv\b", "移动/重命名"),
    (r"\bcp\b", "复制文件"),
    (r"\btar\s+", "解压/打包"),
    (r"\bunzip\b", "解压"),
    (r"\bgit\s+checkout\b", "Git分支切换"),
    (r"\bgit\s+reset\b", "Git重置"),
    (r"\bgit\s+revert\b", "Git回滚"),
]

# ---- 高危工具操作（判定为 CRITICAL） ----
CRITICAL_TOOLS: frozenset[str] = frozenset({
    "block_high_risk_process",
})

# ---- 需确认工具操作（判定为 IRREVERSIBLE） ----
IRREVERSIBLE_TOOLS: frozenset[str] = frozenset({
})

# ---- 需确认工具操作（判定为 REVERSIBLE） ----
REVERSIBLE_TOOLS: frozenset[str] = frozenset({
    "run_terminal_command",
    "run_autonomous_mission",
    "run_risk_demo",
})


class RiskAssessor:
    """四级风险判定器.

    用法:
        assessor = RiskAssessor()
        assessment = assessor.assess_terminal("rm -rf /tmp/foo")
        if assessment.level.needs_confirmation():
            # 需要用户确认
    """

    def assess_terminal(self, command: str, *, sudo: bool = False) -> RiskAssessment:
        """对终端命令进行四级风险判定."""
        cmd = command.strip()
        if not cmd:
            return RiskAssessment(RiskLevel.READONLY, "空命令", "R-EMPTY")

        # 1. 检查 CRITICAL 模式
        for pat, desc in CRITICAL_PATTERNS:
            if re.search(pat, cmd, re.IGNORECASE):
                return RiskAssessment(
                    RiskLevel.CRITICAL,
                    f"高危指令: {desc}",
                    rule_id="R-CRITICAL",
                    suggested_action=f"命令匹配高危规则「{desc}」，需人工审批",
                    requires_backup=True,
                    requires_escalation=True,
                    metadata={"pattern": pat, "description": desc},
                )

        # 2. sudo 下的不可逆操作升级
        if sudo:
            for pat, desc in IRREVERSIBLE_PATTERNS:
                if re.search(pat, cmd, re.IGNORECASE):
                    return RiskAssessment(
                        RiskLevel.IRREVERSIBLE,
                        f"sudo不可逆: {desc}",
                        rule_id="R-SUDO-IRREV",
                        suggested_action=f"sudo操作「{desc}」不可逆，需授权并自动备份",
                        requires_backup=True,
                        metadata={"pattern": pat, "description": desc, "sudo": True},
                    )

        # 3. 检查 IRREVERSIBLE 模式
        for pat, desc in IRREVERSIBLE_PATTERNS:
            if re.search(pat, cmd, re.IGNORECASE):
                return RiskAssessment(
                    RiskLevel.IRREVERSIBLE,
                    f"不可逆: {desc}",
                    rule_id="R-IRREVERSIBLE",
                    suggested_action=f"操作「{desc}」不可逆，需用户明确授权并自动备份",
                    requires_backup=True,
                    metadata={"pattern": pat, "description": desc},
                )

        # 4. 检查 REVERSIBLE 模式
        for pat, desc in REVERSIBLE_PATTERNS:
            if re.search(pat, cmd, re.IGNORECASE):
                return RiskAssessment(
                    RiskLevel.REVERSIBLE,
                    f"可逆操作: {desc}",
                    rule_id="R-REVERSIBLE",
                    suggested_action=f"操作「{desc}」可逆，需用户确认",
                    metadata={"pattern": pat, "description": desc},
                )

        # 5. 默认为只读（观测类命令）
        # 检查是否为常见的只读观测命令
        readonly_prefixes = (
            "ps ", "ss ", "df ", "free ", "uptime", "whoami", "id",
            "uname", "hostname", "cat ", "head ", "tail ", "grep ",
            "ls ", "find ", "last ", "w", "top ", "htop ",
            "journalctl ", "systemctl status", "netstat ", "pgrep ",
            "pidof ", "echo ", "which ", "type ", "file ",
            "lsof ", "vmstat ", "iostat ", "mpstat ",
        )
        for prefix in readonly_prefixes:
            if cmd.lower().startswith(prefix.lower()):
                return RiskAssessment(
                    RiskLevel.READONLY,
                    f"只读观测命令: {prefix.strip()}...",
                    rule_id="R-READONLY",
                    suggested_action="自动放行",
                )

        # 未知命令，保守判定为 REVERSIBLE
        return RiskAssessment(
            RiskLevel.REVERSIBLE,
            "命令未分类，保守判定为可逆操作",
            rule_id="R-UNKNOWN",
            suggested_action="未识别的命令，需用户确认",
        )

    def assess_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> RiskAssessment:
        """对工具调用进行四级风险判定."""
        name = tool_name.lower()

        if name in CRITICAL_TOOLS:
            pid = (arguments or {}).get("pid", "?")
            return RiskAssessment(
                RiskLevel.CRITICAL,
                f"高危工具: {name} (PID={pid})",
                rule_id="R-TOOL-CRITICAL",
                suggested_action=f"拦截进程工具调用，需人工审批",
                requires_backup=True,
                requires_escalation=True,
                metadata={"tool": name, "args": arguments or {}},
            )

        if name in IRREVERSIBLE_TOOLS:
            return RiskAssessment(
                RiskLevel.IRREVERSIBLE,
                f"不可逆工具: {name}",
                rule_id="R-TOOL-IRREV",
                suggested_action="工具操作不可逆，需授权并备份",
                requires_backup=True,
                metadata={"tool": name, "args": arguments or {}},
            )

        if name in REVERSIBLE_TOOLS:
            return RiskAssessment(
                RiskLevel.REVERSIBLE,
                f"可逆工具: {name}",
                rule_id="R-TOOL-REV",
                suggested_action="工具操作可逆，需确认",
                metadata={"tool": name, "args": arguments or {}},
            )

        # 其余工具自动放行（只读工具集）
        return RiskAssessment(
            RiskLevel.READONLY,
            f"只读工具: {name}",
            rule_id="R-TOOL-READONLY",
            suggested_action="自动放行",
            metadata={"tool": name, "args": arguments or {}},
        )
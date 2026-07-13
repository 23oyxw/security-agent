"""PreExecutionAnalyzer — 命令执行前的多维分析.

设计原则（可解释 + 渐进式）:
    每条命令执行前，自动分析：
    1. 命令类型（观测/修改/删除/网络/权限）
    2. 影响范围（会触及哪些文件/路径）
    3. 风险评估（得分 + 可解释因子）
    4. 历史参考（这条/类似命令过去的成功率）
    5. 更安全的替代方案

用法:
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer

    analyzer = PreExecutionAnalyzer()
    report = analyzer.analyze("rm -rf /tmp/cache", context_snapshot)
    # report.risk_score = 0.55
    # report.risk_factors = ["删除操作", "递归删除"]
    # report.safer_alternatives = ["mv /tmp/cache /backup/", "find /tmp/cache -mtime +7 -delete"]
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from security_agent.terminal.context import ContextSnapshot

# ---- 命令分类规则 ----

_COMMAND_PATTERNS: dict[str, list[str]] = {
    "observe": [
        r"^(ls|ll|dir|cat|head|tail|less|more|grep|find|locate|which|whereis|file|stat|du|df|free|top|htop|ps|pgrep|pidof|netstat|ss|ip\s+addr|ip\s+link|ip\s+route|ifconfig|who|w|last|history|echo|pwd|id|whoami|uname|hostname|uptime|date|env|printenv|ulimit|sysctl|getenforce|systemctl\s+status|systemctl\s+is-active|systemctl\s+is-enabled|journalctl|dmesg|auditctl\s+-l)",
    ],
    "modify": [
        r"^(touch|mkdir|cp|mv|tar|gzip|gunzip|zip|unzip|rsync|scp|tee|sed\s+-i|awk\s+.*{.*print|echo\s+.*>|cat\s+.*>>|dd|fallocate|truncate|chmod|chown|chgrp|setfacl|ln|mount|umount)",
    ],
    "delete": [
        r"^(rm|rmdir|unlink|shred|wipe|fstrim)",
    ],
    "network": [
        r"^(curl|wget|nc|ncat|telnet|ssh|scp|sftp|ftp|tcpdump|nmap|ping|traceroute|dig|nslookup|host|iptables|nft|firewall-cmd|ufw)",
    ],
    "privilege": [
        r"^(sudo|su|pkexec|newgrp|chroot|systemctl\s+(start|stop|restart|reload|enable|disable|mask)|service|kill|killall|pkill|xargs\s+kill|nice|renice|ionice|cgroup)",
    ],
}

# 危险模式（触发后风险分显著提高）
_DANGER_PATTERNS: dict[str, float] = {
    r"rm\s+-rf\s+/": 0.99,           # 递归根目录删除
    r"rm\s+-rf\s+\*": 0.85,          # 通配删除
    r">\s*/dev/sd[a-z]": 0.95,       # 直接写块设备
    r"dd\s+if=": 0.80,               # 磁盘操作
    r"mkfs\.": 0.90,                 # 格式化
    r"fdisk\s+|parted\s+": 0.88,     # 分区操作
    r"chmod\s+777": 0.75,            # 过度开放权限
    r"chown\s+-R\s+.*\s+/": 0.90,    # 递归所有者修改根目录
    r":\(\)\s*\{": 0.95,             # fork bomb
    r"wget\s+.*\|\s*sh": 0.92,       # 下载并执行
    r"curl\s+.*\|\s*bash": 0.92,     # 下载并执行
    r"iptables\s+-F": 0.70,          # 清空防火墙规则
    r"kill\s+-9\s+-1": 0.85,         # 杀掉所有进程
    r"shutdown|reboot|init\s+[06]": 0.95,  # 关机/重启
}

# 意图关键词 → 命令映射（渐进式扩展）
_INTENT_TO_COMMANDS: dict[str, list[dict[str, str]]] = {
    "查看磁盘": [
        {"command": "df -h", "type": "observe", "note": "查看磁盘使用率"},
        {"command": "du -sh /var/log/* | sort -rh | head -10", "type": "observe", "note": "查看 /var/log 下最大的 10 个目录"},
    ],
    "查看进程": [
        {"command": "ps aux --sort=-%mem | head -10", "type": "observe", "note": "按内存排序的进程"},
        {"command": "ps aux --sort=-%cpu | head -10", "type": "observe", "note": "按 CPU 排序的进程"},
    ],
    "查看内存": [
        {"command": "free -h", "type": "observe", "note": "查看内存使用"},
        {"command": "vmstat 1 5", "type": "observe", "note": "查看虚拟内存统计（5 次采样）"},
    ],
    "查看网络": [
        {"command": "ss -tunlp", "type": "observe", "note": "查看所有监听端口"},
        {"command": "ss -s", "type": "observe", "note": "查看网络连接摘要"},
    ],
    "清理日志": [
        {"command": "find /var/log -name '*.log' -mtime +30 -delete", "type": "delete", "note": "删除 30 天前的日志"},
        {"command": "journalctl --vacuum-size=500M", "type": "modify", "note": "限制 journal 日志大小到 500MB"},
    ],
    "查看登录": [
        {"command": "last -20", "type": "observe", "note": "最近 20 条登录记录"},
        {"command": "lastb -20", "type": "observe", "note": "最近 20 条失败登录记录"},
    ],
    "查看IO": [
        {"command": "iotop -bon1 | head -20", "type": "observe", "note": "按 IO 排序的进程"},
        {"command": "iostat -x 1 3", "type": "observe", "note": "IO 统计（3 次采样）"},
    ],
}


@dataclass
class PreExecReport:
    """预执行分析报告 — 用户看到的「执行前分析」."""

    command: str
    command_type: str             # observe | modify | delete | network | privilege | mixed
    affected_paths: list[str] = field(default_factory=list)
    danger_matches: list[str] = field(default_factory=list)
    risk_score: float = 0.0       # 0.0 ~ 1.0
    risk_factors: list[str] = field(default_factory=list)
    historical_success_rate: float | None = None  # 0.0~1.0 或 None（无历史）
    similar_commands: list[str] = field(default_factory=list)
    safer_alternatives: list[str] = field(default_factory=list)
    sandbox_dry_run_ok: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command[:200],
            "command_type": self.command_type,
            "affected_paths": self.affected_paths[:10],
            "danger_matches": self.danger_matches,
            "risk_score": round(self.risk_score, 3),
            "risk_factors": self.risk_factors,
            "historical_success_rate": (
                round(self.historical_success_rate, 3)
                if self.historical_success_rate is not None else None
            ),
            "similar_commands": self.similar_commands[:5],
            "safer_alternatives": self.safer_alternatives[:3],
            "sandbox_dry_run_ok": self.sandbox_dry_run_ok,
        }

    @property
    def summary(self) -> str:
        """人类可读的分析摘要."""
        parts = [f"类型={self.command_type}"]
        if self.risk_score > 0.6:
            parts.append(f"风险=高({self.risk_score:.2f})")
        elif self.risk_score > 0.3:
            parts.append(f"风险=中({self.risk_score:.2f})")
        else:
            parts.append(f"风险=低({self.risk_score:.2f})")
        if self.risk_factors:
            parts.append(f"因子={'+'.join(self.risk_factors[:3])}")
        if self.historical_success_rate is not None:
            parts.append(f"历史成功率={self.historical_success_rate:.0%}")
        return " · ".join(parts)


class PreExecutionAnalyzer:
    """命令预执行分析器."""

    def __init__(self):
        self._execution_history: list[dict[str, Any]] = []  # 执行历史（用于相似匹配）

    def analyze(
        self,
        command: str,
        context: ContextSnapshot | None = None,
    ) -> PreExecReport:
        """分析命令并生成预执行报告.

        Args:
            command: 用户要执行的命令
            context: 可选的上下文快照

        Returns:
            PreExecReport — 包含分类/风险/建议
        """
        cmd = command.strip()

        # 1. 命令分类
        cmd_type = self._classify(cmd)

        # 2. 提取受影响的路径
        paths = self._extract_paths(cmd)

        # 3. 危险模式匹配
        dangers, danger_score = self._check_dangers(cmd)

        # 4. 计算风险分数
        risk_score, risk_factors = self._calculate_risk(cmd, cmd_type, dangers, danger_score)

        # 5. 历史查询
        hist_rate, similar = self._lookup_history(cmd)

        # 6. 生成更安全的替代方案
        alternatives = self._suggest_alternatives(cmd, cmd_type, risk_score)

        return PreExecReport(
            command=cmd,
            command_type=cmd_type,
            affected_paths=paths,
            danger_matches=dangers,
            risk_score=risk_score,
            risk_factors=risk_factors,
            historical_success_rate=hist_rate,
            similar_commands=similar,
            safer_alternatives=alternatives,
        )

    def understand_intent(self, intent: str) -> dict[str, Any]:
        """将自然语言意图映射为命令建议.

        Args:
            intent: 用户描述的自然语言意图（如 "查看磁盘空间"）

        Returns:
            {"intent": str, "suggestions": [{"command": str, "type": str, "note": str, "risk_score": float}]}
        """
        intent_lower = intent.lower().strip()

        # 关键词匹配（v0.9 简单实现，后续可接入 LLM）
        best_match = None
        best_score = 0
        for key, commands in _INTENT_TO_COMMANDS.items():
            # 计算关键词重叠度
            key_chars = set(key)
            intent_chars = set(intent_lower)
            overlap = len(key_chars & intent_chars) / max(len(key_chars), 1)
            if overlap > best_score:
                best_score = overlap
                best_match = key

        suggestions = []
        if best_match and best_score > 0.15:
            for cmd_info in _INTENT_TO_COMMANDS[best_match]:
                risk = self._calculate_risk(cmd_info["command"], cmd_info["type"], [], 0)
                suggestions.append({
                    "command": cmd_info["command"],
                    "type": cmd_info["type"],
                    "note": cmd_info["note"],
                    "risk_score": round(risk[0], 3),
                })

        return {
            "intent": intent,
            "matched_keyword": best_match,
            "match_score": round(best_score, 3),
            "suggestions": suggestions,
        }

    # ---- 命令分类 ----

    def _classify(self, command: str) -> str:
        types = []
        for cmd_type, patterns in _COMMAND_PATTERNS.items():
            for pat in patterns:
                if re.match(pat, command, re.IGNORECASE):
                    types.append(cmd_type)
                    break
        if not types:
            return "unknown"
        if len(types) == 1:
            return types[0]
        return "+".join(types)  # "modify+network" 等混合类型

    # ---- 路径提取 ----

    @staticmethod
    def _extract_paths(command: str) -> list[str]:
        """从命令中提取 Unix 路径."""
        paths = re.findall(r'(/[^\s;|&><"]+)', command)
        # 过滤太短的路径
        return [p for p in paths if len(p) > 2][:10]

    # ---- 危险检测 ----

    def _check_dangers(self, command: str) -> tuple[list[str], float]:
        dangers = []
        max_score = 0.0
        for pattern, score in _DANGER_PATTERNS.items():
            if re.search(pattern, command, re.IGNORECASE):
                dangers.append(pattern)
                max_score = max(max_score, score)
        return dangers, max_score

    # ---- 风险评估 ----

    def _calculate_risk(
        self,
        command: str,
        cmd_type: str,
        dangers: list[str],
        danger_score: float,
    ) -> tuple[float, list[str]]:
        """计算风险分数和可解释的风险因子."""
        score = 0.0
        factors = []

        # 基准分：命令类型
        type_baseline = {
            "observe": 0.05,
            "modify": 0.30,
            "delete": 0.55,
            "network": 0.35,
            "privilege": 0.60,
        }
        for t, base in type_baseline.items():
            if t in cmd_type:
                score = max(score, base)
                factors.append(t)

        # 危险模式加分
        if danger_score > 0:
            score = max(score, danger_score)
            factors.append(f"危险模式×{len(dangers)}")

        # 路径风险：操作 /etc, /boot, / 等敏感路径
        sensitive_paths = ["/etc", "/boot", "/root", "/home", "/var/lib", "/proc", "/sys"]
        cmd_lower = command.lower()
        for sp in sensitive_paths:
            if sp in cmd_lower:
                score = min(score + 0.15, 0.95)
                factors.append(f"敏感路径({sp})")
                break

        # 递归操作
        if "-r" in command or "-R" in command or "--recursive" in command:
            if cmd_type in ("delete", "modify", "privilege"):
                score = min(score + 0.10, 0.95)
                factors.append("递归操作")

        # 管道符（复杂命令链）
        if "|" in command:
            score = min(score + 0.05, 0.95)

        return round(score, 3), factors

    # ---- 历史查询 ----

    def _lookup_history(self, command: str) -> tuple[float | None, list[str]]:
        """在历史中查找相似命令."""
        if not self._execution_history:
            return None, []

        # 精确匹配
        exact = [h for h in self._execution_history if h["command"] == command]
        if exact:
            successes = sum(1 for h in exact if h.get("ok", False))
            return successes / len(exact), [h["command"] for h in exact[-3:]]

        # 前缀匹配（如 "find /var/log" 匹配 "find /var/log -name ..."）
        cmd_words = command.split()[:2]
        prefix = " ".join(cmd_words)
        similar = [h for h in self._execution_history if h["command"].startswith(prefix)]
        if similar:
            successes = sum(1 for h in similar if h.get("ok", False))
            return successes / len(similar), [h["command"] for h in similar[-3:]]

        return None, []

    # ---- 替代方案 ----

    def _suggest_alternatives(self, command: str, cmd_type: str, risk_score: float) -> list[str]:
        """如果风险较高，生成更安全的替代方案."""
        if risk_score < 0.5:
            return []

        alternatives = []

        # rm -rf → find + delete（更精确）
        if "rm" in command and ("-rf" in command or "-r" in command):
            paths = self._extract_paths(command)
            if paths:
                alternatives.append(f"# 更安全：先列出再删除\nfind {paths[0]} -type f -name '*.log' -mtime +30 -print | head -20")
                alternatives.append(f"# 确认后再删\nfind {paths[0]} -type f -name '*.log' -mtime +30 -delete")

        # kill -9 → kill 或 systemctl stop
        if "kill -9" in command or "killall -9" in command:
            alternatives.append("# 更安全：先尝试正常终止\nkill <PID>  # 不带 -9")
            alternatives.append("# 或使用服务管理\nsystemctl stop <service>")

        # chmod 777 → 750
        if "chmod 777" in command:
            alternatives.append("# 更安全：使用最小权限\nchmod 750 <path>")

        # 通用建议：备份后再操作
        if risk_score > 0.7:
            alternatives.append("# 更安全：先备份\ncp -a <path> <path>.bak.$(date +%Y%m%d)")

        return alternatives

    # ---- 学习接口 ----

    def record_execution(self, command: str, ok: bool, cmd_type: str = "") -> None:
        """记录一次执行结果（供后续历史查询）."""
        self._execution_history.append({
            "command": command,
            "type": cmd_type or self._classify(command),
            "ok": ok,
            "timestamp": time.time(),
        })
        # 限制历史大小
        if len(self._execution_history) > 500:
            self._execution_history = self._execution_history[-500:]

    def history_stats(self) -> dict[str, Any]:
        """执行历史的统计信息."""
        if not self._execution_history:
            return {"total": 0}
        total = len(self._execution_history)
        successes = sum(1 for h in self._execution_history if h.get("ok"))
        return {
            "total": total,
            "success": successes,
            "failure": total - successes,
            "success_rate": round(successes / total, 3) if total else None,
        }

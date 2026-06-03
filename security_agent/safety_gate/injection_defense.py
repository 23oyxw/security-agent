"""注入防御模块 — Prompt/命令/Shell/SQL/路径遍历 多维度注入检测.

与 Qt C++ 端 injection_test_node.cpp 对应，提供 Python 后端的注入防护能力。
作为三层防御 L1 静态风险评估的组成部分，在执行前识别恶意注入载荷。

设计原则:
  - 多层检测金字塔: 静态正则(Fast) → 语义异常(Medium) → LLM辅助(Slow,可选)
  - 编码绕过对抗: URL编码/Unicode/Base64 解码后再检测
  - 白名单+黑名单混合: 已知攻击模式(黑名单) + 异常结构(熵检测)
  - 阻断策略: 严重度 >= BLOCK_THRESHOLD 阻断, WARN级别记录审计
"""

from __future__ import annotations

import re
import base64
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# 配置常量
# =============================================================================

BLOCK_THRESHOLD = 85       # 严重度 >= 此值阻断
WARN_THRESHOLD = 60         # 严重度 >= 此值告警
MAX_DECODE_DEPTH = 3        # 最大递归解码深度(对抗多层编码绕过)


class InjectionType(Enum):
    """注入攻击类型."""
    NONE = "none"
    PROMPT_INJECTION = "prompt_injection"        # 提示词注入
    COMMAND_INJECTION = "command_injection"       # 命令注入
    SQL_INJECTION = "sql_injection"               # SQL注入
    SHELL_INJECTION = "shell_injection"           # Shell注入
    PATH_TRAVERSAL = "path_traversal"             # 路径遍历
    XSS = "xss"                                   # 跨站脚本
    SSRF = "ssrf"                                 # 服务端请求伪造
    ENCODING_ATTACK = "encoding_attack"           # 编码混淆攻击


@dataclass
class InjectionRule:
    """单条注入检测规则."""
    pattern: str                            # 正则表达式
    rule_type: InjectionType               # 注入类型
    severity: int = 50                      # 严重度 0-100
    description: str = ""                   # 规则描述
    # 是否仅检测解码后的文本(原始文本中不直接匹配)
    decode_only: bool = False


@dataclass
class InjectionResult:
    """注入检测结果."""
    triggered: bool = False
    injection_type: InjectionType = InjectionType.NONE
    matched_rules: list[dict[str, Any]] = field(default_factory=list)
    severity: int = 0                        # 最高严重度
    block: bool = False                      # 是否应阻断
    decode_chain_applied: bool = False       # 是否经过解码
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "triggered": self.triggered,
            "injection_type": self.injection_type.value,
            "matched_count": len(self.matched_rules),
            "max_severity": self.severity,
            "block": self.block,
            "decode_chain_applied": self.decode_chain_applied,
            "matched_rules": self.matched_rules,
            "details": self.details,
        }


# =============================================================================
# 注入规则库 (40+ 条规则, 覆盖6种注入类型)
# =============================================================================

INJECTION_RULES: list[InjectionRule] = [

    # ── Prompt 注入(10条) ──
    InjectionRule(
        r"(?i)ignore\s+(all\s+)?previous\s+instructions", InjectionType.PROMPT_INJECTION,
        90, "忽略前置指令攻击 — 尝试覆盖系统提示词"),
    InjectionRule(
        r"(?i)(you\s+are\s+now|your\s+new\s+role\s+is|you\s+are\s+no\s+longer)",
        InjectionType.PROMPT_INJECTION, 85, "角色劫持 — 尝试重新定义Agent身份"),
    InjectionRule(
        r"(?i)(override|disregard|ignore)\s+(system\s+)?(prompt|message|instruction)",
        InjectionType.PROMPT_INJECTION, 95, "覆盖系统提示词 — 尝试绕过安全约束"),
    InjectionRule(
        r"(?i)(do\s+not\s+follow|don't\s+follow)\s+(previous|above|system)",
        InjectionType.PROMPT_INJECTION, 85, "指令劫持 — 告诉模型忽略上游指令"),
    InjectionRule(
        r"(?i)(pretend|act\s+as|roleplay|impersonate)\s+(you\s+are|as\s+an?)",
        InjectionType.PROMPT_INJECTION, 75, "角色扮演攻击 — 尝试让模型扮演危险角色"),
    InjectionRule(
        r"(?i)(DAN|jailbreak|developer\s*mode|god\s*mode|unrestricted)",
        InjectionType.PROMPT_INJECTION, 90, "越狱关键词 — DAN/God Mode 等已知越狱模式"),
    InjectionRule(
        r"(?i)(output\s+your\s+system\s+prompt|show\s+me\s+your\s+instructions|reveal\s+your\s+prompt)",
        InjectionType.PROMPT_INJECTION, 85, "提示词泄露攻击 — 尝试提取系统提示词"),
    InjectionRule(
        r"(?i)(from\s+now\s+on\s+you\s+(must|will|should|are))",
        InjectionType.PROMPT_INJECTION, 80, "持续性指令覆盖 — 尝试长期改变模型行为"),
    InjectionRule(
        r"(?i)(\\[SYSTEM\\]|\\[INST\\]|\\[PROMPT\\]|<\\|system\\|>|<\\|user\\|>)",
        InjectionType.PROMPT_INJECTION, 80, "结构化注入标签 — 伪造系统/用户标识"),
    InjectionRule(
        r"(?i)(reply\s+in\s+chinese|respond\s+only\s+with|translate\s+everything)",
        InjectionType.PROMPT_INJECTION, 50, "语言切换注入 — 低风险但可疑"),

    # ── 命令注入(10条) ──
    InjectionRule(
        r"\brm\s+-rf\b", InjectionType.COMMAND_INJECTION,
        100, "危险删除命令 — rm -rf 递归强制删除"),
    InjectionRule(
        r";\s*(rm|shutdown|reboot|halt|poweroff)\b", InjectionType.COMMAND_INJECTION,
        95, "命令链注入 — 分号后跟危险命令"),
    InjectionRule(
        r"\|\s*(sh|bash|zsh|ksh|csh)\b", InjectionType.COMMAND_INJECTION,
        90, "管道执行Shell — 通过管道将输出传给Shell解释器"),
    InjectionRule(
        r"\$\([^)]*\)", InjectionType.COMMAND_INJECTION,
        80, "命令替换 $(...) — 在命令中嵌入子命令执行"),
    InjectionRule(
        r"`[^`]+`", InjectionType.COMMAND_INJECTION,
        80, "反引号命令执行 — 旧式命令替换语法"),
    InjectionRule(
        r"&&\s*(rm|shutdown|reboot|mkfs|dd\s+if=)",
        InjectionType.COMMAND_INJECTION, 95, "&& 链危险命令 — 前命令成功后执行破坏操作"),
    InjectionRule(
        r"\|\|\s*(rm|shutdown|reboot)", InjectionType.COMMAND_INJECTION,
        85, "|| 链回退攻击 — 前命令失败后执行危险操作"),
    InjectionRule(
        r">\s*/dev/[a-z]+\b.*\b(rm|shutdown)", InjectionType.COMMAND_INJECTION,
        85, "重定向后注入 — 利用输出重定向隐藏恶意命令"),
    InjectionRule(
        r"\b(chmod\s+777|chmod\s+-R\s+777|chown\s+-R\s+root)",
        InjectionType.COMMAND_INJECTION, 85, "权限提升 — 777 完全开放或 root 属主变更"),
    InjectionRule(
        r"\b(wget|curl)\s+.*\|\s*(sh|bash)", InjectionType.COMMAND_INJECTION,
        95, "远程脚本执行 — curl/wget 管道到 Shell"),

    # ── SQL 注入(8条) ──
    InjectionRule(
        r"(?i)\bDROP\s+TABLE\b", InjectionType.SQL_INJECTION,
        100, "SQL DROP TABLE — 删除数据库表"),
    InjectionRule(
        r"(?i)\bTRUNCATE\s+TABLE\b", InjectionType.SQL_INJECTION,
        100, "SQL TRUNCATE TABLE — 清空数据库表"),
    InjectionRule(
        r"(?i)\bDELETE\s+FROM\b", InjectionType.SQL_INJECTION,
        95, "SQL DELETE FROM — 删除数据记录"),
    InjectionRule(
        r"(?i)('\s*OR\s+'1'='1|'\s*OR\s+1=1)", InjectionType.SQL_INJECTION,
        85, "SQL OR 注入 — 经典条件永真绕过"),
    InjectionRule(
        r"(?i)--\s*$", InjectionType.SQL_INJECTION,
        70, "SQL 注释截断 — 通过注释消除后续条件"),
    InjectionRule(
        r"(?i)\bUNION\s+SELECT\b", InjectionType.SQL_INJECTION,
        90, "SQL UNION SELECT — 联合查询窃取数据"),
    InjectionRule(
        r"(?i)\bEXEC\s*\([^)]*\)", InjectionType.SQL_INJECTION,
        90, "SQL EXEC — 动态执行SQL语句"),
    InjectionRule(
        r"(?i)\b(SELECT|INSERT|UPDATE)\s+.*\b(FROM|INTO|SET)\b.*(--|#|/\*)",
        InjectionType.SQL_INJECTION, 75, "SQL 语句 + 注释 — 可疑的SQL拼接模式"),

    # ── Shell 注入(7条) ──
    InjectionRule(
        r"\$\{[^}]*\}", InjectionType.SHELL_INJECTION,
        85, "Shell 变量替换 ${...} — 可能注入恶意变量"),
    InjectionRule(
        r"\beval\s*\([^)]*\)", InjectionType.SHELL_INJECTION,
        95, "eval 执行 — 将字符串作为代码执行"),
    InjectionRule(
        r"\bexec\s*\([^)]*\)", InjectionType.SHELL_INJECTION,
        95, "exec 执行 — 替换当前进程执行命令"),
    InjectionRule(
        r"\bsystem\s*\([^)]*\)", InjectionType.SHELL_INJECTION,
        90, "system 调用 — C标准库system()函数调用"),
    InjectionRule(
        r"\b(subprocess|popen|os\.system|os\.popen)\s*\([^)]*\)",
        InjectionType.SHELL_INJECTION, 85, "Python subprocess/os 调用 — 系统命令执行"),
    InjectionRule(
        r"/dev/null\s*;", InjectionType.SHELL_INJECTION,
        80, "重定向后注入 — 丢弃正常输出后执行恶意命令"),
    InjectionRule(
        r"\b__import__\s*\(|importlib|compile\s*\(",
        InjectionType.SHELL_INJECTION, 80, "Python 动态导入/编译 — 代码注入检测"),

    # ── 路径遍历(5条) ──
    InjectionRule(
        r"\.\./\.\./|\.\.\\\.\.\\", InjectionType.PATH_TRAVERSAL,
        75, "目录遍历 — 通过 ../ 访问父目录"),
    InjectionRule(
        r"/etc/(passwd|shadow|sudoers|hosts)", InjectionType.PATH_TRAVERSAL,
        90, "敏感系统文件 — 尝试访问 /etc 下的安全文件"),
    InjectionRule(
        r"%2e%2e%2f|%2e%2e/|\.%2e/", InjectionType.PATH_TRAVERSAL,
        70, "URL编码目录遍历 — 利用编码绕过过滤", decode_only=True),
    InjectionRule(
        r"\.\.%252f|\.%252e/", InjectionType.PATH_TRAVERSAL,
        75, "双层URL编码目录遍历 — 二次编码绕过", decode_only=True),
    InjectionRule(
        r"(?i)file:///(etc|proc|sys|dev)/", InjectionType.PATH_TRAVERSAL,
        85, "file协议访问敏感目录 — 通过文件协议读取系统文件"),

    # ── 编码混淆攻击(3条) — 检测异常编码密度 ──
    InjectionRule(
        r"(?i)(%[0-9a-f]{2}){5,}", InjectionType.ENCODING_ATTACK,
        60, "高密度URL编码 — 连续5+个编码字符，可疑"),
    InjectionRule(
        r"(?i)(\\x[0-9a-f]{2}){5,}", InjectionType.ENCODING_ATTACK,
        65, "高密度Hex编码 — 连续5+个 \\x 转义字符"),
    InjectionRule(
        r"(?i)(\\u[0-9a-f]{4}){4,}", InjectionType.ENCODING_ATTACK,
        65, "高密度Unicode编码 — 连续4+个 \\uXXXX 转义字符"),
]


# 危险命令白名单(允许的命令前缀)
SAFE_COMMAND_PREFIXES: list[str] = [
    "ls", "cat", "head", "tail", "grep", "find", "wc", "sort", "uniq",
    "ps", "top", "htop", "df", "du", "free", "uptime", "uname",
    "ping", "traceroute", "nslookup", "dig", "host",
    "netstat", "ss", "lsof", "ifconfig", "ip",
    "who", "w", "last", "history",
    "echo", "date", "which",
    "docker ps", "docker images", "docker logs", "docker inspect",
    "systemctl status", "journalctl",
    "git log", "git status", "git diff", "git branch",
]


# =============================================================================
# 解码对抗 — 多层递归解码
# =============================================================================


def _decode_chain(text: str, max_depth: int = MAX_DECODE_DEPTH) -> tuple[str, bool]:
    """递归解码，对抗编码绕过.

    解码顺序: URL编码 → Unicode转义 → Base64
    递归直到文本不再变化或达到最大深度.
    """
    original = text
    decoded = text
    changed = False
    depth = 0

    while depth < max_depth:
        prev = decoded

        # 第一层: URL 解码
        try:
            url_decoded = urllib.parse.unquote(prev)
            # 如果解码后有明显改善(长度变化且无异常)
            if url_decoded != prev and len(url_decoded) > 0:
                prev = url_decoded
                changed = True
        except Exception:
            pass

        # 第二层: Unicode 转义解码
        try:
            unicode_decoded = prev.encode('utf-8').decode('unicode_escape')
            # 只接受非纯ASCII的合理解码
            if unicode_decoded != prev:
                printable = sum(1 for c in unicode_decoded if c.isprintable() or c in '\n\r\t')
                if printable / max(len(unicode_decoded), 1) > 0.7:
                    prev = unicode_decoded
                    changed = True
        except Exception:
            pass

        # 第三层: Base64 解码 (仅当文本看起来像 Base64)
        if re.match(r'^[A-Za-z0-9+/=]{20,}$', prev):
            try:
                b64_decoded = base64.b64decode(prev).decode('utf-8', errors='replace')
                if b64_decoded != prev:
                    prev = b64_decoded
                    changed = True
            except Exception:
                pass

        if prev == decoded:
            break

        decoded = prev
        depth += 1

    return decoded, changed


# =============================================================================
# 注入检测引擎
# =============================================================================


class InjectionDefense:
    """注入防御引擎 — 多维度检测 + 编码对抗 + 分级响应.

    使用方式:
        defense = InjectionDefense()
        result = defense.scan("rm -rf /")
        if result.block:
            raise SecurityException("检测到命令注入攻击")
    """

    def __init__(self, block_threshold: int = BLOCK_THRESHOLD):
        self.block_threshold = block_threshold
        self._rules = INJECTION_RULES

    def scan(
        self,
        text: str,
        *,
        enable_types: set[InjectionType] | None = None,
        apply_decode_chain: bool = True,
    ) -> InjectionResult:
        """对输入文本执行注入扫描.

        Args:
            text: 待检测文本
            enable_types: 启用的检测类型集合(None=全部)
            apply_decode_chain: 是否应用递归解码对抗

        Returns:
            InjectionResult 包含触发状态和匹配详情
        """
        if not text or not text.strip():
            return InjectionResult(triggered=False)

        matched_rules: list[dict[str, Any]] = []
        max_severity = 0
        decode_applied = False

        # 拼接检测目标: 原始 + 解码后
        scan_targets = [("raw", text)]

        if apply_decode_chain:
            decoded, changed = _decode_chain(text)
            if changed and decoded != text:
                decode_applied = True
                scan_targets.append(("decoded", decoded))

        # 执行规则匹配
        for target_label, target_text in scan_targets:
            for rule in self._rules:
                # 类型过滤
                if enable_types and rule.rule_type not in enable_types:
                    continue

                # decode_only 规则只在解码后文本中匹配
                if rule.decode_only and target_label != "decoded":
                    continue

                try:
                    regex = re.compile(rule.pattern, re.IGNORECASE | re.MULTILINE)
                    match = regex.search(target_text)
                    if match:
                        matched_rules.append({
                            "type": rule.rule_type.value,
                            "severity": rule.severity,
                            "description": rule.description,
                            "matched_text": match.group()[:100],  # 截断避免日志爆炸
                            "detected_in": target_label,
                        })
                        max_severity = max(max_severity, rule.severity)
                except re.error:
                    continue

        # 去重(同类型+同描述只保留最高严重度)
        unique_matches: list[dict[str, Any]] = []
        seen = set()
        for m in sorted(matched_rules, key=lambda x: -x["severity"]):
            key = (m["type"], m["description"])
            if key not in seen:
                seen.add(key)
                unique_matches.append(m)

        triggered = len(unique_matches) > 0
        injection_type = (
            InjectionType(unique_matches[0]["type"])
            if triggered
            else InjectionType.NONE
        )

        return InjectionResult(
            triggered=triggered,
            injection_type=injection_type,
            matched_rules=unique_matches,
            severity=max_severity,
            block=triggered and max_severity >= self.block_threshold,
            decode_chain_applied=decode_applied,
            details={
                "scan_targets_count": len(scan_targets),
                "total_rules_checked": len(self._rules),
                "block_threshold": self.block_threshold,
            },
        )

    def quick_check(self, text: str) -> bool:
        """快速安全检查 — 返回是否安全(True=安全)."""
        result = self.scan(text, apply_decode_chain=False)
        return not result.block

    def is_command_safe(self, command: str) -> bool:
        """检查单条命令是否安全(白名单+注入检测)."""
        # 1. 白名单检查
        stripped = command.strip().lstrip()
        for prefix in SAFE_COMMAND_PREFIXES:
            if stripped.startswith(prefix):
                return True

        # 2. 注入检测
        result = self.scan(command)
        return not result.block

    @staticmethod
    def sanitize(text: str) -> str:
        """对输入文本做基础清理(去除危险字符).

        注意: 这不是万能的! 只做最低限度的脱敏.
        """
        # 去除空字节和不可打印控制字符(保留换行)
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        return sanitized


# =============================================================================
# 全局单例
# =============================================================================

_global_defense: InjectionDefense | None = None


def get_injection_defense() -> InjectionDefense:
    """获取全局注入防御实例."""
    global _global_defense
    if _global_defense is None:
        _global_defense = InjectionDefense()
    return _global_defense
"""日志分析 Skill — 多源日志采集、模式识别、异常检测、告警关联."""

from __future__ import annotations

import json
import os
import re
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.security.redact import redact_text
from security_agent.timeutil import now_iso
from security_agent.agent.budget import get_budget_agent

# ---- 异常日志模式库 ----
LOG_PATTERNS: dict[str, dict[str, Any]] = {
    "brute_force": {
        "name": "暴力破解",
        "severity": "严重",
        "pattern": r"(Failed password|authentication failure|invalid user).*from\s+(\S+)",
        "description": "短时间内多次登录失败，疑似暴力破解",
        "threshold": 5,  # 同一 IP 在窗口期内触发次数
        "window_sec": 300,
    },
    "privilege_escalation": {
        "name": "提权尝试",
        "severity": "严重",
        "pattern": r"(sudo:\s+\S+\s+:.*COMMAND=|su\[\d+\].*to\s+root)",
        "description": "检测到 sudo/su 提权操作",
        "threshold": 1,
        "window_sec": 60,
    },
    "service_crash": {
        "name": "服务崩溃",
        "severity": "高",
        "pattern": r"(segfault|core dumped|killed.*oom|out of memory|oom-killer)",
        "description": "进程崩溃或被 OOM Killer 终止",
        "threshold": 1,
        "window_sec": 60,
        "flags": re.IGNORECASE,
    },
    "disk_error": {
        "name": "磁盘错误",
        "severity": "高",
        "pattern": r"(I/O error|EXT4-fs error|read-only filesystem|disk full|No space left)",
        "description": "磁盘 I/O 错误或文件系统异常",
        "threshold": 1,
        "window_sec": 60,
        "flags": re.IGNORECASE,
    },
    "network_anomaly": {
        "name": "网络异常",
        "severity": "中",
        "pattern": r"(nf_conntrack.*table full|nf_conntrack:.*dropping|TCP:.*time wait bucket table overflow)",
        "description": "连接跟踪表满或 TCP 异常",
        "threshold": 1,
        "window_sec": 120,
        "flags": re.IGNORECASE,
    },
    "firewall_block": {
        "name": "防火墙拦截",
        "severity": "中",
        "pattern": r"(iptables.*DROP|iptables.*REJECT|UFW BLOCK|firewalld.*REJECT)",
        "description": "防火墙规则触发拦截",
        "threshold": 10,
        "window_sec": 60,
        "flags": re.IGNORECASE,
    },
    "ssh_anomaly": {
        "name": "SSH 异常",
        "severity": "高",
        "pattern": r"(Received disconnect from|connection closed by.*\[preauth\]|POSSIBLE BREAK-IN ATTEMPT)",
        "description": "SSH 连接异常或疑似入侵尝试",
        "threshold": 3,
        "window_sec": 120,
    },
    "cron_anomaly": {
        "name": "Cron 异常",
        "severity": "中",
        "pattern": r"(CRON\[\d+\].*FAILED|crontab.*permission denied|anacron.*error)",
        "description": "定时任务执行失败或权限异常",
        "threshold": 1,
        "window_sec": 300,
    },
    "selinux_audit": {
        "name": "SELinux/安全审计",
        "severity": "中",
        "pattern": r"(AVC.*denied|type=AVC|kysec.*denied|kysec.*blocked)",
        "description": "SELinux 或麒麟安全模块拒绝操作",
        "threshold": 3,
        "window_sec": 300,
        "flags": re.IGNORECASE,
    },
    "kernel_warning": {
        "name": "内核告警",
        "severity": "高",
        "pattern": r"(kernel:.*BUG:|kernel:.*WARNING:|kernel:.*panic|kernel:.*oops)",
        "description": "内核级别错误或告警",
        "threshold": 1,
        "window_sec": 60,
        "flags": re.IGNORECASE,
    },
}

# 日志源路径（按优先级）
LOG_SOURCES = [
    "/var/log/syslog",
    "/var/log/messages",
    "/var/log/auth.log",
    "/var/log/secure",
    "/var/log/kern.log",
    "/var/log/daemon.log",
    "/var/log/cron.log",
    "/var/log/audit/audit.log",
]

# 最近匹配事件（内存中保留）
_MAX_MATCHES = 500


@dataclass
class LogMatch:
    """一条日志匹配记录."""

    ts: str
    pattern_name: str
    severity: str
    log_file: str
    line_number: int
    matched_text: str
    extracted_ip: str = ""
    raw_line: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "pattern_name": self.pattern_name,
            "severity": self.severity,
            "log_file": self.log_file,
            "line_number": self.line_number,
            "matched_text": self.matched_text[:300],
            "extracted_ip": self.extracted_ip,
            "raw_line": redact_text(self.raw_line[:500]),
        }


class LogAnalyzerSkill(SkillBase):
    """日志分析 Skill — 多源日志采集、模式匹配、异常检测."""

    def __init__(self) -> None:
        self._recent_matches: deque[LogMatch] = deque(maxlen=_MAX_MATCHES)
        self._file_offsets: dict[str, int] = {}  # 增量读取的文件偏移

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="log_analyzer",
            display_name="日志分析",
            description="多源日志采集、模式识别、异常检测、暴力破解/提权/崩溃等关键事件识别",
            version="1.0.0",
            tags=("logging", "detection", "anomaly", "security"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="log_scan",
                description="扫描系统日志，检测异常模式（暴力破解、提权、崩溃、磁盘错误等）",
                parameters={
                    "type": "object",
                    "properties": {
                        "lines": {
                            "type": "integer",
                            "description": "每个日志文件扫描的行数",
                            "default": 500,
                        },
                        "patterns": {
                            "type": "string",
                            "description": "逗号分隔的模式名（留空=全部）",
                            "default": "",
                        },
                    },
                    "required": [],
                },
                handler=self._tool_scan,
            ),
            ToolDef(
                name="log_tail",
                description="实时跟踪日志文件末尾，返回最近 N 行",
                parameters={
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "日志文件路径（留空自动选择）",
                            "default": "",
                        },
                        "lines": {"type": "integer", "default": 50},
                        "filter": {
                            "type": "string",
                            "description": "过滤关键词",
                            "default": "",
                        },
                    },
                    "required": [],
                },
                handler=self._tool_tail,
            ),
            ToolDef(
                name="log_search",
                description="在日志中搜索关键词或正则表达式",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词或正则"},
                        "file": {"type": "string", "default": ""},
                        "max_results": {"type": "integer", "default": 20},
                        "use_regex": {"type": "boolean", "default": False},
                    },
                    "required": ["query"],
                },
                handler=self._tool_search,
            ),
            ToolDef(
                name="log_patterns",
                description="列出所有已知的异常日志模式及其统计",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_patterns,
            ),
            ToolDef(
                name="log_recent_matches",
                description="获取最近检测到的异常日志匹配记录",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 30},
                        "severity": {"type": "string", "default": ""},
                    },
                    "required": [],
                },
                handler=self._tool_recent_matches,
            ),
            ToolDef(
                name="log_incremental_scan",
                description="增量扫描（仅扫描上次以来的新内容），适合持续监控",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_incremental_scan,
            ),
        ]

    def get_rules(self) -> list[str]:
        return [
            "日志分析结果须引用具体日志行和时间戳，禁止编造日志内容",
            "敏感信息（密码、token）在展示前自动打码",
            "暴力破解检测需关联 IP 和时间窗口，避免单次失败误报",
        ]

    # ---- 核心扫描 ----

    def scan_logs(
        self,
        lines: int = 500,
        pattern_filter: list[str] | None = None,
    ) -> list[LogMatch]:
        """扫描系统日志，返回匹配的异常记录."""
        matches: list[LogMatch] = []
        ts = now_iso()

        for log_path in LOG_SOURCES:
            path = Path(log_path)
            if not path.exists() or not os.access(path, os.R_OK):
                continue

            try:
                # 读取末尾 N 行
                all_lines = _tail_file(path, lines)
            except (PermissionError, OSError):
                continue

            for line_num, line in enumerate(all_lines, 1):
                for pat_name, pat_info in LOG_PATTERNS.items():
                    if pattern_filter and pat_name not in pattern_filter:
                        continue
                    flags = pat_info.get("flags", 0)
                    m = re.search(pat_info["pattern"], line, flags)
                    if not m:
                        continue
                    extracted_ip = ""
                    if m.lastindex and m.lastindex >= 2:
                        extracted_ip = m.group(2)
                    match = LogMatch(
                        ts=ts,
                        pattern_name=pat_name,
                        severity=pat_info["severity"],
                        log_file=log_path,
                        line_number=line_num,
                        matched_text=m.group(0)[:300],
                        extracted_ip=extracted_ip,
                        raw_line=line.strip()[:500],
                    )
                    matches.append(match)
                    self._recent_matches.append(match)

        return matches

    def incremental_scan(self) -> list[LogMatch]:
        """增量扫描 — 仅读取上次偏移之后的新内容."""
        matches: list[LogMatch] = []
        ts = now_iso()

        for log_path in LOG_SOURCES:
            path = Path(log_path)
            if not path.exists() or not os.access(path, os.R_OK):
                continue

            try:
                file_size = path.stat().st_size
                offset = self._file_offsets.get(log_path, 0)

                # 文件被截断/轮转（大小变小）→ 从头读
                if file_size < offset:
                    offset = 0

                with path.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    new_lines = f.readlines()
                    self._file_offsets[log_path] = f.tell()

                for line_num, line in enumerate(new_lines, 1):
                    for pat_name, pat_info in LOG_PATTERNS.items():
                        flags = pat_info.get("flags", 0)
                        m = re.search(pat_info["pattern"], line, flags)
                        if not m:
                            continue
                        extracted_ip = ""
                        if m.lastindex and m.lastindex >= 2:
                            extracted_ip = m.group(2)
                        match = LogMatch(
                            ts=ts,
                            pattern_name=pat_name,
                            severity=pat_info["severity"],
                            log_file=log_path,
                            line_number=offset // 80 + line_num,  # 近似行号
                            matched_text=m.group(0)[:300],
                            extracted_ip=extracted_ip,
                            raw_line=line.strip()[:500],
                        )
                        matches.append(match)
                        self._recent_matches.append(match)
            except (PermissionError, OSError):
                continue

        return matches

    def search_logs(
        self,
        query: str,
        log_file: str = "",
        max_results: int = 20,
        use_regex: bool = False,
    ) -> list[dict[str, Any]]:
        """在日志中搜索关键词或正则."""
        results: list[dict[str, Any]] = []
        sources = [log_file] if log_file else LOG_SOURCES

        for log_path in sources:
            path = Path(log_path)
            if not path.exists() or not os.access(path, os.R_OK):
                continue
            try:
                lines = _tail_file(path, 2000)
                for line_num, line in enumerate(lines, 1):
                    matched = False
                    if use_regex:
                        matched = bool(re.search(query, line, re.IGNORECASE))
                    else:
                        matched = query.lower() in line.lower()
                    if matched:
                        results.append({
                            "file": log_path,
                            "line": line_num,
                            "text": redact_text(line.strip()[:500]),
                        })
                        if len(results) >= max_results:
                            return results
            except (PermissionError, OSError):
                continue

        return results

    def get_pattern_stats(self) -> dict[str, Any]:
        """统计各模式的匹配次数."""
        counts: Counter[str] = Counter()
        for m in self._recent_matches:
            counts[m.pattern_name] += 1
        return {
            "total_matches": len(self._recent_matches),
            "pattern_counts": dict(counts),
            "patterns": {
                name: {
                    "display_name": info["name"],
                    "severity": info["severity"],
                    "description": info["description"],
                    "threshold": info["threshold"],
                    "window_sec": info["window_sec"],
                    "matched_count": counts.get(name, 0),
                }
                for name, info in LOG_PATTERNS.items()
            },
        }

    def get_recent_matches(
        self,
        limit: int = 30,
        severity_filter: str = "",
    ) -> list[dict[str, Any]]:
        """获取最近匹配记录."""
        matches = list(self._recent_matches)
        if severity_filter:
            matches = [m for m in matches if m.severity == severity_filter]
        return [m.to_dict() for m in matches[-limit:]]

    # ---- 告警回调 ----

    async def on_alert(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """响应监控告警 — 关联日志上下文."""
        etype = str(event.get("type", ""))
        if etype in ("登录失败暴破", "高危新进程", "敏感文件变更"):
            # 增量扫描新日志
            new_matches = self.incremental_scan()
            if new_matches:
                return {
                    "action": "log_context",
                    "new_matches": len(new_matches),
                    "details": [m.to_dict() for m in new_matches[:10]],
                    "recommendation": f"发现 {len(new_matches)} 条新异常日志关联事件，建议排查",
                }
        return None

    # ---- 工具处理器 ----

    async def _tool_scan(self, lines: int = 500, patterns: str = "") -> str:
        pat_filter = [p.strip() for p in patterns.split(",") if p.strip()] if patterns else None
        matches = self.scan_logs(lines=lines, pattern_filter=pat_filter)

        # 当匹配数量较多时，使用 Budget Agent 进行批量总结
        ai_summary = None
        if len(matches) >= 10 and config.BUDGET_API_KEY:
            try:
                budget_agent = get_budget_agent()
                ai_summary = budget_agent.summarize_logs([m.to_dict() for m in matches])
            except Exception:
                ai_summary = None  # 失败时静默回退到原始结果

        result = {
            "total_matches": len(matches),
            "matches": [m.to_dict() for m in matches],
            "sources_scanned": [p for p in LOG_SOURCES if Path(p).exists()],
            "timestamp": now_iso(),
        }
        if ai_summary:
            result["ai_summary"] = ai_summary

        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_tail(self, file: str = "", lines: int = 50, filter: str = "") -> str:
        target = file or (LOG_SOURCES[0] if Path(LOG_SOURCES[0]).exists() else "")
        if not target or not Path(target).exists():
            return json.dumps({"error": f"日志文件不存在: {target}"}, ensure_ascii=False)
        try:
            all_lines = _tail_file(Path(target), lines)
            if filter:
                all_lines = [l for l in all_lines if filter.lower() in l.lower()]
            return json.dumps(
                {"file": target, "lines": len(all_lines), "content": [redact_text(l.rstrip()) for l in all_lines]},
                ensure_ascii=False,
                indent=2,
            )
        except (PermissionError, OSError) as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    async def _tool_search(self, query: str, file: str = "", max_results: int = 20, use_regex: bool = False) -> str:
        results = self.search_logs(query, log_file=file, max_results=max_results, use_regex=use_regex)
        return json.dumps({"query": query, "results_count": len(results), "results": results}, ensure_ascii=False, indent=2)

    async def _tool_patterns(self) -> str:
        return json.dumps(self.get_pattern_stats(), ensure_ascii=False, indent=2)

    async def _tool_recent_matches(self, limit: int = 30, severity: str = "") -> str:
        return json.dumps(self.get_recent_matches(limit, severity), ensure_ascii=False, indent=2)

    async def _tool_incremental_scan(self) -> str:
        matches = self.incremental_scan()
        return json.dumps(
            {"new_matches": len(matches), "matches": [m.to_dict() for m in matches], "timestamp": now_iso()},
            ensure_ascii=False,
            indent=2,
        )


def _tail_file(path: Path, lines: int) -> list[str]:
    """高效读取文件末尾 N 行."""
    try:
        # 对大文件用块读取
        size = path.stat().st_size
        chunk = min(size, lines * 200)  # 假设每行平均 200 字节
        with path.open("rb") as f:
            f.seek(max(0, size - chunk))
            data = f.read().decode("utf-8", errors="replace")
        all_lines = data.splitlines()
        return all_lines[-lines:]
    except (OSError, PermissionError):
        return []


# ---- 全局实例 ----
skill_instance = LogAnalyzerSkill()
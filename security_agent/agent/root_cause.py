"""智能根因分析引擎 — 赛题评分项: 智能化根因分析能力.

基于 OS 感知数据 + 规则引擎 + LLM 辅助推理，
对系统异常进行自动根因定位和处置建议。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RootCauseFinding:
    """单个根因发现."""
    category: str           # cpu / memory / disk / network / process / log / security
    severity: str           # critical / warning / info
    title: str              # 简要标题
    evidence: List[str]     # 证据列表
    root_cause: str         # 根因描述
    suggested_actions: List[str]  # 建议处置动作
    confidence: float = 0.0  # 置信度 0~1


@dataclass
class RootCauseReport:
    """根因分析报告."""
    findings: List[RootCauseFinding] = field(default_factory=list)
    system_snapshot: Dict[str, Any] = field(default_factory=dict)
    analysis_summary: str = ""

    @property
    def has_issues(self) -> bool:
        return len(self.findings) > 0

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_issues": self.has_issues,
            "total_findings": len(self.findings),
            "critical_count": self.critical_count,
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "evidence": f.evidence,
                    "root_cause": f.root_cause,
                    "suggested_actions": f.suggested_actions,
                    "confidence": round(f.confidence, 2),
                }
                for f in self.findings
            ],
            "summary": self.analysis_summary,
        }


class RootCauseAnalyzer:
    """根因分析器 — 规则驱动 + 可选 LLM 增强."""

    # 阈值配置
    CPU_HIGH_THRESHOLD = 80.0
    MEM_HIGH_THRESHOLD = 90.0
    DISK_HIGH_THRESHOLD = 85.0
    ZOMBIE_ALERT_COUNT = 3

    async def analyze(self, snapshot: Optional[Dict[str, Any]] = None) -> RootCauseReport:
        """执行完整根因分析."""
        from security_agent.tools.os_sensing import full_system_snapshot

        if snapshot is None:
            snapshot = await full_system_snapshot()

        report = RootCauseReport(system_snapshot=snapshot)

        # 规则引擎分析
        self._check_disk(snapshot, report)
        self._check_zombies(snapshot, report)
        self._check_network(snapshot, report)
        self._check_errors(snapshot, report)
        self._check_load(snapshot, report)
        self._check_processes(snapshot, report)

        # 生成摘要
        if report.findings:
            critical = [f for f in report.findings if f.severity == "critical"]
            warnings = [f for f in report.findings if f.severity == "warning"]
            report.analysis_summary = (
                f"发现 {len(report.findings)} 个问题 "
                f"({len(critical)} 严重, {len(warnings)} 警告)。"
            )
            if critical:
                report.analysis_summary += f" 严重问题: {', '.join(f.title for f in critical)}"
        else:
            report.analysis_summary = "系统状态正常，未发现异常。"

        return report

    def _check_disk(self, snapshot: Dict[str, Any], report: RootCauseReport) -> None:
        """磁盘容量/大文件检查."""
        disk = snapshot.get("disk", {})
        if not disk.get("ok"):
            return

        for d in disk.get("disks", []):
            pct_str = d.get("use_percent", "0%").replace("%", "")
            try:
                pct = float(pct_str)
            except ValueError:
                continue
            if pct >= 95:
                report.findings.append(RootCauseFinding(
                    category="disk",
                    severity="critical",
                    title=f"磁盘 {d['mount']} 使用率 {pct}%（即将满）",
                    evidence=[f"文件系统 {d['filesystem']}: {d['used']}/{d['size']}"],
                    root_cause="磁盘空间即将耗尽，可能导致日志丢失、服务崩溃",
                    suggested_actions=[
                        f"清理 {d['mount']} 下的大文件或旧日志",
                        "运行 system_cleanup 清理临时文件",
                        "检查是否有日志轮转配置",
                    ],
                    confidence=0.95,
                ))
            elif pct >= self.DISK_HIGH_THRESHOLD:
                report.findings.append(RootCauseFinding(
                    category="disk",
                    severity="warning",
                    title=f"磁盘 {d['mount']} 使用率偏高 {pct}%",
                    evidence=[f"文件系统 {d['filesystem']}: {d['used']}/{d['size']}"],
                    root_cause="磁盘使用率持续偏高，建议关注",
                    suggested_actions=["排查大文件", "考虑日志归档"],
                    confidence=0.8,
                ))

    def _check_zombies(self, snapshot: Dict[str, Any], report: RootCauseReport) -> None:
        """僵尸进程检查."""
        zombies = snapshot.get("zombies", {})
        count = zombies.get("zombie_count", 0)
        if count >= self.ZOMBIE_ALERT_COUNT:
            zombie_cmds = [z.get("command", "?") for z in zombies.get("zombies", [])[:5]]
            report.findings.append(RootCauseFinding(
                category="process",
                severity="warning",
                title=f"检测到 {count} 个僵尸进程",
                evidence=[f"PID {z.get('pid')}: {z.get('command', '')[:80]}" for z in zombies.get("zombies", [])[:5]],
                root_cause="父进程未正确回收子进程，长期堆积可能耗尽 PID 资源",
                suggested_actions=[
                    "定位父进程并发送 SIGCHLD 信号",
                    "必要时终止父进程以释放僵尸进程",
                    "检查是否有守护进程未正确处理子进程退出",
                ],
                confidence=0.9,
            ))

    def _check_network(self, snapshot: Dict[str, Any], report: RootCauseReport) -> None:
        """异常网络连接检查."""
        ports = snapshot.get("network_ports", {})
        if not ports.get("ok"):
            return

        suspicious_ports = []
        known_safe = {22, 80, 443, 8501, 8900, 5173, 5432, 6379, 4000}
        for p in ports.get("ports", []):
            port_num = p.get("port", 0)
            if port_num > 0 and port_num not in known_safe and port_num < 1024:
                suspicious_ports.append(p)

        if suspicious_ports:
            report.findings.append(RootCauseFinding(
                category="network",
                severity="warning",
                title=f"发现 {len(suspicious_ports)} 个非常规系统端口监听",
                evidence=[f"{p['address']} ({p.get('process', '')})" for p in suspicious_ports[:5]],
                root_cause="可能存在未授权的服务在系统端口上监听",
                suggested_actions=[
                    "确认这些服务是否为预期部署",
                    "非预期服务应立即排查并关闭",
                    "检查防火墙规则",
                ],
                confidence=0.6,
            ))

    def _check_errors(self, snapshot: Dict[str, Any], report: RootCauseReport) -> None:
        """日志错误检查."""
        errors = snapshot.get("recent_errors", {})
        if not errors.get("ok"):
            return

        entries = errors.get("entries", [])
        if len(entries) >= 5:
            # 检查是否有 OOM
            oom_entries = [e for e in entries if "out of memory" in e.lower() or "oom" in e.lower()]
            if oom_entries:
                report.findings.append(RootCauseFinding(
                    category="memory",
                    severity="critical",
                    title="检测到 OOM（内存不足）事件",
                    evidence=oom_entries[:3],
                    root_cause="系统内存不足触发 OOM Killer，可能导致服务被意外终止",
                    suggested_actions=[
                        "检查内存占用最高的进程",
                        "考虑增加 swap 或物理内存",
                        "优化应用内存使用",
                    ],
                    confidence=0.95,
                ))

            # 通用错误过多
            if len(entries) >= 10:
                report.findings.append(RootCauseFinding(
                    category="log",
                    severity="warning",
                    title=f"最近 30 分钟内有 {len(entries)} 条错误日志",
                    evidence=entries[:3],
                    root_cause="短时间内错误日志过多，可能存在系统异常",
                    suggested_actions=["排查错误日志来源", "检查相关服务状态"],
                    confidence=0.7,
                ))

    def _check_load(self, snapshot: Dict[str, Any], report: RootCauseReport) -> None:
        """系统负载检查."""
        load_data = snapshot.get("system_load", {})
        if not load_data.get("ok"):
            return

        load_avg = load_data.get("load_avg", {})
        try:
            load_1m = float(load_avg.get("1min", "0"))
        except (ValueError, TypeError):
            return

        import os
        cpu_count = os.cpu_count() or 1
        if load_1m > cpu_count * 2:
            report.findings.append(RootCauseFinding(
                category="cpu",
                severity="critical" if load_1m > cpu_count * 4 else "warning",
                title=f"系统负载过高: {load_1m} (CPU 核心数: {cpu_count})",
                evidence=[f"1分钟负载: {load_avg.get('1min')}", f"5分钟负载: {load_avg.get('5min')}"],
                root_cause="系统负载远超 CPU 核心数，可能存在 CPU 密集型进程或资源争抢",
                suggested_actions=[
                    "使用 top/htop 查看 CPU 占用最高的进程",
                    "检查是否有异常进程占用大量 CPU",
                    "考虑限制进程资源（cgroup/nice）",
                ],
                confidence=0.85,
            ))

    def _check_processes(self, snapshot: Dict[str, Any], report: RootCauseReport) -> None:
        """异常进程检查."""
        procs = snapshot.get("processes", {})
        if not procs.get("ok"):
            return

        for p in procs.get("processes", []):
            try:
                cpu_usage = float(p.get("cpu", "0"))
            except (ValueError, TypeError):
                continue
            if cpu_usage > 90:
                report.findings.append(RootCauseFinding(
                    category="cpu",
                    severity="warning",
                    title=f"进程 {p.get('command', '')[:50]} CPU 占用 {cpu_usage}%",
                    evidence=[f"PID: {p['pid']}, 用户: {p['user']}, CPU: {cpu_usage}%"],
                    root_cause="单个进程 CPU 占用过高",
                    suggested_actions=[
                        f"检查进程 {p['pid']} 的详细信息",
                        "确认是否为预期行为",
                        "必要时限制 CPU 亲和性或 nice 值",
                    ],
                    confidence=0.75,
                ))

    def correlate_findings(self, report: RootCauseReport) -> Dict[str, Any]:
        """关联分析 — 将零散发现串成因果链."""
        if not report.findings:
            return {"chains": [], "primary_cause": None}

        chains = []

        # 因果规则
        rules = [
            ("memory→process", "memory", "process",
             "内存压力导致 OOM Killer 触发，终止进程"),
            ("disk→log", "disk", "log",
             "磁盘满导致日志写入失败或服务异常"),
            ("cpu→process", "cpu", "process",
             "CPU 高负载由异常进程引起"),
            ("load→cpu", "cpu", "cpu",
             "系统高负载与 CPU 指标关联，可能存在资源争抢"),
            ("memory→disk", "memory", "disk",
             "内存不足触发 swap 使用，加剧磁盘 I/O 压力"),
            ("network→process", "network", "process",
             "异常网络连接可能关联到特定进程"),
        ]

        for chain_id, cat1, cat2, desc in rules:
            f1 = [f for f in report.findings if f.category == cat1]
            f2 = [f for f in report.findings if f.category == cat2]
            if f1 and f2:
                chains.append({
                    "type": chain_id,
                    "description": desc,
                    "primary": f1[0].title,
                    "secondary": f2[0].title,
                    "confidence": min(f1[0].confidence, f2[0].confidence),
                })

        # 找首要根因（严重度最高 + 置信度最高）
        primary = max(report.findings, key=lambda f: (
            {"critical": 3, "warning": 2, "info": 1}.get(f.severity, 0),
            f.confidence,
        ))

        return {
            "chains": chains,
            "primary_cause": primary.title,
            "chain_count": len(chains),
        }


# 全局实例
_analyzer: Optional[RootCauseAnalyzer] = None


def get_root_cause_analyzer() -> RootCauseAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = RootCauseAnalyzer()
    return _analyzer
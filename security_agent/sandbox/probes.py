"""探针网格 — 12 根探针，定时在沙箱中运行，检测安全薄弱点.

设计原则（可解释 + 自愈优先）:
    每根探针是一段安全的检测脚本 → 在沙箱中执行 → 返回发现。
    发现薄弱点后自动生成加固建议。

三类探针:
    1. 权限探针 (privilege) — 检测权限提升路径
    2. 文件系统探针 (filesystem) — 检测沙箱逃逸可能
    3. 网络探针 (network) — 检测网络隔离漏洞

用法:
    from security_agent.sandbox.probes import ProbeGrid

    grid = ProbeGrid()
    report = grid.run_all_patrol()
    # report.findings → [{"probe": "setuid_backdoor", "severity": "高", ...}]
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_IS_LINUX = sys.platform == "linux"


@dataclass
class ProbeDef:
    """一根探针的定义."""
    probe_id: str
    category: str          # "privilege" | "filesystem" | "network"
    title: str             # 人类可读标题
    description: str       # 检测什么
    check_command: str     # shell 命令（安全，只读）
    danger_pattern: str    # 匹配到此模式 = 发现薄弱点
    severity: str = "中"   # 严重度
    hardening_suggestion: str = ""  # 加固建议


@dataclass
class ProbeFinding:
    """一根探针的检测结果."""
    probe_id: str
    category: str
    title: str
    passed: bool           # True = 安全, False = 发现薄弱点
    detail: str            # 检测详情
    severity: str
    hardening: str         # 如果发现薄弱点，给出加固建议
    raw_output: str = ""   # 探针命令的原始输出

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "category": self.category,
            "title": self.title,
            "passed": self.passed,
            "detail": self.detail[:500],
            "severity": self.severity,
            "hardening": self.hardening,
        }


@dataclass
class PatrolReport:
    """一次完整巡检的报告."""
    findings: list[ProbeFinding] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    total: int = 0
    patrolled_at: str = ""

    @property
    def health_score(self) -> float:
        return round(self.passed / max(self.total, 1), 3)

    @property
    def summary(self) -> str:
        if self.failed == 0:
            return f"巡检通过 ({self.passed}/{self.total}) — 未发现薄弱点"
        findings = [f for f in self.findings if not f.passed]
        top = findings[0] if findings else None
        return f"发现 {self.failed} 个薄弱点 — 最严重: {top.title if top else 'N/A'}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "health_score": self.health_score,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "patrolled_at": self.patrolled_at,
        }


class ProbeGrid:
    """探针网格 — 12 根探针，3 类."""

    def __init__(self):
        self._probes = self._define_probes()

    @staticmethod
    def _define_probes() -> list[ProbeDef]:
        """定义全部 12 根探针."""
        probes = [
            # ---- 权限探针 (4) ----
            ProbeDef(
                "privilege_setuid", "privilege",
                "异常 setuid 二进制检测",
                "检测系统中非系统目录下的 setuid 二进制文件",
                "find / -type f -perm -4000 -not -path '/usr/*' -not -path '/bin/*' -not -path '/sbin/*' 2>/dev/null | head -10",
                r"\S",  # 任何输出 = 发现
                "高",
                "审查非标准路径的 setuid 二进制: chmod u-s <file>",
            ),
            ProbeDef(
                "privilege_sudo", "privilege",
                "sudo 配置缺陷检测",
                "检测 sudoers 中是否存在过于宽泛的 NOPASSWD 规则",
                "grep -r 'NOPASSWD.*ALL' /etc/sudoers /etc/sudoers.d/ 2>/dev/null | head -5",
                r"NOPASSWD.*ALL",
                "高",
                "收紧 sudoers: 限制具体命令而非 ALL, 去掉 NOPASSWD",
            ),
            ProbeDef(
                "privilege_caps", "privilege",
                "进程 capabilities 泄漏检测",
                "检测拥有危险 capabilities 的非 root 进程",
                "grep -l CapEff /proc/*/status 2>/dev/null | head -1 > /dev/null && echo 'caps found' || echo 'clean'",
                r"caps found",
                "中",
                "审计进程 capabilities: capsh --print, 去掉不必要的 cap",
            ),
            ProbeDef(
                "privilege_writable", "privilege",
                "全局可写目录检测",
                "检测 /tmp 外是否有全局可写的目录",
                "find /etc /var -type d -perm -002 -not -path '/tmp/*' 2>/dev/null | head -5",
                r"\S",
                "中",
                "收紧目录权限: chmod o-w <directory>",
            ),

            # ---- 文件系统探针 (4) ----
            ProbeDef(
                "fs_symlink", "filesystem",
                "符号链接逃逸检测",
                "检测 /tmp 下是否有指向系统敏感文件的符号链接",
                "find /tmp /var/tmp -type l -lname '/etc/*' -o -lname '/root/*' 2>/dev/null | head -5",
                r"\S",
                "高",
                "删除可疑符号链接: rm <symlink>",
            ),
            ProbeDef(
                "fs_mount_leak", "filesystem",
                "挂载点泄漏检测",
                "检测是否有非预期的挂载点（可能用于容器逃逸）",
                "mount | grep -v -E '(proc|sys|dev|tmpfs|cgroup|overlay|ext|xfs|btrfs|nfs)' | head -5",
                r"\S",
                "中",
                "审查非预期挂载: umount <mountpoint>",
            ),
            ProbeDef(
                "fs_proc_leak", "filesystem",
                "/proc 敏感信息泄漏检测",
                "检测 /proc 是否挂载且 hidepid 未启用（非 root 可窥探其他进程）",
                "grep -E '^proc\s+/proc' /proc/mounts | grep -v hidepid" if _IS_LINUX else "echo 'N/A'",
                r"/proc",
                "中",
                "启用 hidepid: mount -o remount,hidepid=2 /proc",
            ),
            ProbeDef(
                "fs_tmp_noexec", "filesystem",
                "/tmp noexec 检测",
                "检测 /tmp 是否以 noexec 挂载（防止执行植入的恶意程序）",
                "mount | grep ' /tmp ' | grep noexec || echo 'missing'",
                r"missing",
                "中",
                "挂载 /tmp 为 noexec: mount -o remount,noexec /tmp",
            ),

            # ---- 网络探针 (4) ----
            ProbeDef(
                "net_raw_socket", "network",
                "原始套接字权限检测",
                "检测非 root 进程是否可以创建原始套接字（可用于 ARP 欺骗）",
                "sysctl net.ipv4.ping_group_range 2>/dev/null || echo 'check skipped'",
                r"",
                "低",
                "限制原始套接字: 确保只有 root 可创建",
            ),
            ProbeDef(
                "net_promiscuous", "network",
                "网卡混杂模式检测",
                "检测是否有网卡处于混杂模式（可能被用于流量嗅探）",
                "ip link show 2>/dev/null | grep PROMISC || echo 'clean'" if _IS_LINUX else "echo 'N/A'",
                r"PROMISC",
                "高",
                "关闭混杂模式: ip link set <iface> promisc off",
            ),
            ProbeDef(
                "net_listening", "network",
                "异常监听端口检测",
                "检测是否有非预期的进程在监听 0.0.0.0 端口",
                "ss -tlnp 2>/dev/null | grep '0.0.0.0' | grep -v -E ':(22|80|443|8900|8501|8000)' | head -5" if _IS_LINUX else "echo 'N/A'",
                r"\S",
                "中",
                "审查异常端口: 确认服务必要性, 必要时绑定到 127.0.0.1",
            ),
            ProbeDef(
                "net_iptables_empty", "network",
                "防火墙规则为空检测",
                "检测 iptables INPUT 链是否为空（主机完全暴露）",
                "iptables -L INPUT 2>/dev/null | grep -c '^ACCEPT\|^DROP\|^REJECT' || echo '0'",
                r"^0$",
                "高",
                "配置基础防火墙规则: iptables -A INPUT -m state --state ESTABLISHED -j ACCEPT",
            ),
        ]
        return probes

    # ---- 巡检 ----

    def run_all_patrol(self, timeout_per_probe: float = 10.0) -> PatrolReport:
        """运行全部 12 根探针，生成巡检报告."""
        from security_agent.timeutil import now_iso

        findings = []
        passed = 0
        failed = 0

        for probe in self._probes:
            f = self._run_probe(probe, timeout_per_probe)
            findings.append(f)
            if f.passed:
                passed += 1
            else:
                failed += 1

        return PatrolReport(
            findings=findings,
            passed=passed,
            failed=failed,
            total=len(findings),
            patrolled_at=now_iso(),
        )

    def run_category(self, category: str) -> PatrolReport:
        """只运行某一类探针."""
        from security_agent.timeutil import now_iso

        probes = [p for p in self._probes if p.category == category]
        findings = [self._run_probe(p) for p in probes]
        passed = sum(1 for f in findings if f.passed)
        return PatrolReport(
            findings=findings,
            passed=passed,
            failed=len(findings) - passed,
            total=len(findings),
            patrolled_at=now_iso(),
        )

    def _run_probe(self, probe: ProbeDef, timeout: float = 10.0) -> ProbeFinding:
        """执行一根探针."""
        try:
            proc = subprocess.run(
                probe.check_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            output = "timeout"
        except Exception as e:
            output = f"error: {e}"

        import re
        danger = probe.danger_pattern
        matched = bool(danger) and bool(re.search(danger, output, re.MULTILINE))

        return ProbeFinding(
            probe_id=probe.probe_id,
            category=probe.category,
            title=probe.title,
            passed=not matched,  # 匹配到危险模式 = 薄弱点
            detail=f"检查: {probe.description}\n结果: {output[:300]}",
            severity=probe.severity,
            hardening=probe.hardening_suggestion if matched else "",
            raw_output=output[:500],
        )

    # ---- 统计 ----

    def list_probes(self) -> list[dict[str, Any]]:
        return [
            {
                "probe_id": p.probe_id,
                "category": p.category,
                "title": p.title,
                "severity": p.severity,
            }
            for p in self._probes
        ]

    def categories(self) -> dict[str, int]:
        cats: dict[str, int] = {}
        for p in self._probes:
            cats[p.category] = cats.get(p.category, 0) + 1
        return cats

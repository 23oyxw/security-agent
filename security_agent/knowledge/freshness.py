"""FreshnessChecker — 知识新鲜度检测：自动发现过时和缺失的知识.

设计原则（自愈优先）:
    知识不会自己更新 — 需要系统持续检测：
    1. 过时检测 — Playbook 引用在系统中是否还存在
    2. 缺口发现 — 最近高频告警是否缺少对应 Playbook
    3. 活跃度 — 哪些 Playbook 长期未被触发（可能已无用）

用法:
    from security_agent.knowledge.freshness import FreshnessChecker

    checker = FreshnessChecker()
    stale = checker.find_stale()         # 过时的 Playbook
    gaps = checker.find_gaps()            # 知识缺口
    report = checker.full_report()        # 完整健康报告
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from security_agent import config


@dataclass
class StaleKnowledge:
    """一条过时/可疑的知识."""
    playbook_id: str
    title: str
    reason: str
    severity: str = "中"       # 过期严重度
    suggestion: str = ""       # 建议操作

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbook_id": self.playbook_id,
            "title": self.title,
            "reason": self.reason,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


@dataclass
class KnowledgeGap:
    """一个知识缺口 — 有事件但无对应 Playbook."""
    gap_topic: str             # 缺失的知识主题
    recent_event_count: int    # 最近相关事件数
    suggested_title: str = ""  # 建议创建的 Playbook 标题
    severity: str = "中"

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_topic": self.gap_topic,
            "recent_events": self.recent_event_count,
            "suggested_title": self.suggested_title,
            "severity": self.severity,
        }


@dataclass
class FreshnessReport:
    """知识新鲜度完整报告."""
    total_playbooks: int = 0
    stale: list[StaleKnowledge] = field(default_factory=list)
    gaps: list[KnowledgeGap] = field(default_factory=list)
    dormant: list[str] = field(default_factory=list)   # 长期未触发的 Playbook ID
    health_score: float = 1.0
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_playbooks": self.total_playbooks,
            "stale_count": len(self.stale),
            "gap_count": len(self.gaps),
            "dormant_count": len(self.dormant),
            "health_score": round(self.health_score, 3),
            "stale": [s.to_dict() for s in self.stale],
            "gaps": [g.to_dict() for g in self.gaps],
            "dormant": self.dormant[:10],
            "checked_at": self.checked_at,
        }

    @property
    def summary(self) -> str:
        parts = []
        if self.stale:
            parts.append(f"{len(self.stale)} 条知识可能过时")
        if self.gaps:
            parts.append(f"{len(self.gaps)} 个知识缺口")
        if self.dormant:
            parts.append(f"{len(self.dormant)} 条知识长期未使用")
        if not parts:
            return "知识库健康，未发现问题"
        return " · ".join(parts)


class FreshnessChecker:
    """知识新鲜度检测器."""

    def __init__(self):
        self._usage_path = config.DATA_DIR / "playbook_usage.json"
        self._alerts_dir = config.DATA_DIR / "alerts"
        self._dormant_threshold_days = 30  # 30 天未使用 → 休眠

    def find_stale(self, *, check_system: bool = False) -> list[StaleKnowledge]:
        """发现可能过时的 Playbook.

        Args:
            check_system: 是否检查系统命令/路径（Windows 上较慢，默认 False）
        """
        stale = []
        try:
            from security_agent.knowledge.playbooks import PLAYBOOKS
            pbs = list(PLAYBOOKS)
        except ImportError:
            return stale

        for p in pbs:
            reasons = []

            # 检查 1: 引用的命令是否还存在
            if check_system:
                for action in p.suggested_actions[:2]:
                    cmd = action.split()[0] if action else ""
                    if cmd and len(cmd) > 1 and not shutil.which(cmd):
                        reasons.append(f"命令 '{cmd}' 在系统中不存在")

            # 检查 2: 引用的路径是否存在
            if check_system:
                for kw in p.keywords[:3]:
                    if kw.startswith("/") and not Path(kw).exists():
                        reasons.append(f"路径 '{kw}' 不存在")

            if reasons:
                stale.append(StaleKnowledge(
                    playbook_id=p.id,
                    title=p.title,
                    reason="; ".join(reasons),
                    severity="中",
                    suggestion=f"请检查 {p.id} 是否仍然适用，考虑更新或归档",
                ))

        return stale

    def find_gaps(self) -> list[KnowledgeGap]:
        """发现知识缺口 — 最近高频告警类型缺少对应 Playbook."""
        gaps = []
        try:
            from security_agent.knowledge.playbooks import PLAYBOOKS
            pbs = list(PLAYBOOKS)
        except ImportError:
            return gaps

        # 收集所有已覆盖的 threat_tag
        covered_tags = set()
        for p in pbs:
            covered_tags.update(p.threat_tags)

        # 从最近的告警中提取高频类型
        recent_types = self._recent_alert_types(limit=50)
        for alert_type, count in recent_types.items():
            if count >= 3:  # 出现 3 次以上 → 值得关注
                # 检查是否有 Playbook 覆盖
                tag = alert_type.lower().replace(" ", "_")
                if tag not in covered_tags and alert_type not in covered_tags:
                    gaps.append(KnowledgeGap(
                        gap_topic=alert_type,
                        recent_event_count=count,
                        suggested_title=f"自动生成: {alert_type}处置方案",
                        severity="中" if count < 10 else "高",
                    ))

        return gaps

    def find_dormant(self, threshold_days: int | None = None) -> list[str]:
        """发现长期未使用的 Playbook."""
        threshold = threshold_days or self._dormant_threshold_days
        usage = self._load_usage()

        dormant = []
        for pb_id, last_used in usage.get("last_used", {}).items():
            days_since = (time.time() - last_used) / 86400
            if days_since > threshold:
                dormant.append(pb_id)

        return dormant

    def full_report(self) -> FreshnessReport:
        """完整的新鲜度健康报告."""
        from security_agent.timeutil import now_iso

        try:
            from security_agent.knowledge.playbooks import PLAYBOOKS
            total = len(PLAYBOOKS)
        except ImportError:
            total = 0

        stale = self.find_stale()
        gaps = self.find_gaps()
        dormant = self.find_dormant()

        # 健康分：扣分项
        deductions = len(stale) * 0.05 + len(gaps) * 0.08 + len(dormant) * 0.03
        health = max(0.0, 1.0 - deductions)

        return FreshnessReport(
            total_playbooks=total,
            stale=stale,
            gaps=gaps,
            dormant=dormant,
            health_score=round(health, 3),
            checked_at=now_iso(),
        )

    # ---- 使用追踪 ----

    def record_usage(self, playbook_id: str) -> None:
        """记录一次 Playbook 使用."""
        usage = self._load_usage()
        if "last_used" not in usage:
            usage["last_used"] = {}
        if "hit_count" not in usage:
            usage["hit_count"] = {}

        usage["last_used"][playbook_id] = time.time()
        usage["hit_count"][playbook_id] = usage["hit_count"].get(playbook_id, 0) + 1

        import json
        self._usage_path.parent.mkdir(parents=True, exist_ok=True)
        self._usage_path.write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")

    def usage_stats(self) -> dict[str, Any]:
        """Playbook 使用统计."""
        return self._load_usage()

    # ---- 内部 ----

    def _load_usage(self) -> dict[str, Any]:
        if not self._usage_path.exists():
            return {}
        try:
            import json
            return json.loads(self._usage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _recent_alert_types(self, limit: int = 50) -> dict[str, int]:
        """从最近告警中提取高频类型."""
        type_counts: dict[str, int] = {}
        events_path = self._alerts_dir / "events.jsonl"
        if not events_path.exists():
            return type_counts

        try:
            import json
            lines = events_path.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines[-limit:]):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    etype = event.get("type", "")
                    if etype:
                        type_counts[etype] = type_counts.get(etype, 0) + 1
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass

        return type_counts

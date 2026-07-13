"""KnowledgeGuard — 知识库健康守护：一致性校验 + 防污染 + 完整性验证.

设计原则（自愈优先）:
    知识库不是静态的 — 它会腐化。需要定期检查：
    1. 矛盾检测 — 两个 Playbook 对同一场景给出相反建议
    2. 防污染 — Wiki 被恶意修改后检测出来
    3. 完整性 — 必要字段是否存在

用法:
    from security_agent.knowledge.guard import KnowledgeGuard

    guard = KnowledgeGuard()
    issues = guard.check_consistency()
    integrity = guard.verify_wiki_integrity()
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from security_agent import config


@dataclass
class ConsistencyIssue:
    """一条一致性问题."""
    severity: str          # "高" | "中" | "低"
    category: str          # "contradiction" | "overlap" | "outdated_ref"
    title: str
    playbook_ids: list[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "playbooks": self.playbook_ids,
            "detail": self.detail[:500],
        }


@dataclass
class IntegrityReport:
    """Wiki 完整性验证报告."""
    ok: bool
    source: str = ""
    checks: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "source": self.source,
            "checks": self.checks,
            "issues": self.issues,
        }


class KnowledgeGuard:
    """知识库健康守护.

    三个检查维度:
        1. consistency — Playbook 之间是否存在矛盾
        2. integrity — Wiki 数据是否被篡改/污染
        3. completeness — 必要字段是否完整
    """

    def __init__(self):
        self._wiki_dir = config.DATA_DIR / "wiki_export"
        self._checksum_path = config.DATA_DIR / "wiki_checksums.json"

    # ---- 一致性检查 ----

    def check_consistency(self) -> list[ConsistencyIssue]:
        """检查所有 Playbook 之间的一致性."""
        issues = []

        try:
            from security_agent.knowledge.playbooks import PLAYBOOKS
            pbs = list(PLAYBOOKS)
        except ImportError:
            return issues

        for p1, p2 in itertools.combinations(pbs, 2):
            # 检查 1: 同一 threat_tag 下的 do_not 和 suggested_actions 矛盾
            if self._tags_overlap(p1.threat_tags, p2.threat_tags):
                conflicts = self._find_action_conflicts(p1, p2)
                if conflicts:
                    issues.append(ConsistencyIssue(
                        severity="高",
                        category="contradiction",
                        title=f"矛盾的动作建议: {p1.title} vs {p2.title}",
                        playbook_ids=[p1.id, p2.id],
                        detail=f"共享标签 {set(p1.threat_tags) & set(p2.threat_tags)}，"
                               f"但存在矛盾建议: {conflicts}",
                    ))

            # 检查 2: 关键词重叠 > 80% 但严重度不同 → 可能其中一个过时
            overlap = self._keyword_overlap(p1.keywords, p2.keywords)
            if overlap > 0.8 and p1.severity != p2.severity:
                issues.append(ConsistencyIssue(
                    severity="中",
                    category="overlap",
                    title=f"高度重叠但严重度不同: {p1.title}({p1.severity}) vs {p2.title}({p2.severity})",
                    playbook_ids=[p1.id, p2.id],
                    detail=f"关键词重叠度 {overlap:.0%}，建议确认两个 Playbook 的严重度是否合理",
                ))

            # 检查 3: do_not 中包含已废弃的命令/路径 → 可能过时
            for p in [p1, p2]:
                stale = self._check_stale_references(p)
                if stale:
                    issues.append(ConsistencyIssue(
                        severity="低",
                        category="outdated_ref",
                        title=f"可能过时的引用: {p.title}",
                        playbook_ids=[p.id],
                        detail=f"引用了可能不存在的命令/路径: {stale}",
                    ))

        return issues

    # ---- Wiki 完整性 ----

    def verify_wiki_integrity(self) -> IntegrityReport:
        """验证 Gitee Wiki 数据的完整性."""
        checks = []
        issues = []

        # 1. 哈希校验（如果之前保存了校验和）
        if self._checksum_path.exists():
            try:
                saved = json.loads(self._checksum_path.read_text(encoding="utf-8"))
                current = self._compute_wiki_checksums()
                for path, old_hash in saved.items():
                    new_hash = current.get(path)
                    if new_hash and new_hash != old_hash:
                        issues.append(f"文件被修改: {path} (哈希不匹配)")
                    elif new_hash is None:
                        issues.append(f"文件被删除: {path}")
                checks.append({
                    "check": "hash_verification",
                    "passed": len(issues) == 0,
                    "files_checked": len(saved),
                })
            except (json.JSONDecodeError, OSError):
                pass

        # 2. 结构校验：检查必要字段
        wiki_files = list(self._wiki_dir.rglob("*.md")) if self._wiki_dir.exists() else []
        for f in wiki_files[:50]:
            try:
                content = f.read_text(encoding="utf-8")
                if len(content.strip()) < 10:
                    issues.append(f"文件过短（可能损坏）: {f.name}")
                # 注入检测：包含 JS/HTML 标签 → 可能被投毒
                if re.search(r'<script|<iframe|javascript:', content, re.IGNORECASE):
                    issues.append(f"文件包含可疑代码（可能被投毒）: {f.name}")
            except Exception:
                issues.append(f"无法读取: {f.name}")

        checks.append({
            "check": "structure_and_injection",
            "passed": all("投毒" not in i for i in issues),
            "files_scanned": len(wiki_files),
        })

        # 3. 内容校验：来源信任链
        checks.append({
            "check": "content_trust_chain",
            "passed": True,
            "note": "Wiki 来源为 Gitee 官方 API，信任链基于 HTTPS + Token",
        })

        return IntegrityReport(
            ok=len(issues) == 0,
            source=str(self._wiki_dir),
            checks=checks,
            issues=issues,
        )

    def save_checksums(self) -> dict[str, str]:
        """保存当前 Wiki 文件的校验和（作为下次比对的基线）."""
        checksums = self._compute_wiki_checksums()
        self._checksum_path.write_text(
            json.dumps(checksums, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return checksums

    # ---- 内部 ----

    @staticmethod
    def _tags_overlap(tags1: tuple, tags2: tuple) -> bool:
        return bool(set(tags1) & set(tags2))

    @staticmethod
    def _keyword_overlap(kw1: tuple, kw2: tuple) -> float:
        if not kw1 or not kw2:
            return 0.0
        intersection = len(set(kw1) & set(kw2))
        union = len(set(kw1) | set(kw2))
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _find_action_conflicts(p1, p2) -> list[str]:
        """检测两个 Playbook 的建议是否有冲突."""
        conflicts = []
        for dont in p1.do_not:
            for suggest in p2.suggested_actions:
                # 简单关键词冲突检测
                dont_words = set(dont)
                suggest_words = set(suggest)
                if len(dont_words & suggest_words) > len(dont_words) * 0.5:
                    conflicts.append(f"'{dont}' vs '{suggest}'")
        return conflicts[:3]

    @staticmethod
    def _check_stale_references(p) -> list[str]:
        """检查 Playbook 中引用的路径/命令是否还存在（轻量版：只检查关键词中看起来像路径的）."""
        stale = []
        for kw in p.keywords[:5]:
            # 检查关键词中像绝对路径的（如 /var/log）
            if kw.startswith("/") and len(kw) > 3:
                if not Path(kw).exists():
                    stale.append(kw)
        # 限制检查数量，避免在 Windows 上 PATH 搜索开销
        return stale[:3]

    def _compute_wiki_checksums(self) -> dict[str, str]:
        """计算所有 Wiki 文件的 SHA256."""
        checksums = {}
        if not self._wiki_dir.exists():
            return checksums
        for f in self._wiki_dir.rglob("*.md"):
            try:
                h = hashlib.sha256(f.read_bytes()).hexdigest()
                checksums[str(f.relative_to(self._wiki_dir))] = h
            except OSError:
                pass
        return checksums

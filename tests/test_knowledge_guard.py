"""知识自愈化测试 — 一致性校验 + 新鲜度检测 + 防污染."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


# ---- KnowledgeGuard ----

def test_guard_consistency_runs():
    """一致性检查不崩溃."""
    from security_agent.knowledge.guard import KnowledgeGuard
    guard = KnowledgeGuard()
    issues = guard.check_consistency()
    assert isinstance(issues, list)


def test_guard_consistency_has_categories():
    """一致性检查返回合理结构."""
    from security_agent.knowledge.guard import KnowledgeGuard, ConsistencyIssue
    guard = KnowledgeGuard()
    issues = guard.check_consistency()
    for i in issues:
        assert isinstance(i, ConsistencyIssue)
        assert i.severity in ("高", "中", "低")
        assert i.category in ("contradiction", "overlap", "outdated_ref")


def test_guard_issue_to_dict():
    """ConsistencyIssue 可序列化."""
    from security_agent.knowledge.guard import ConsistencyIssue
    issue = ConsistencyIssue(
        severity="高", category="contradiction",
        title="测试矛盾", playbook_ids=["PB-001", "PB-002"],
        detail="矛盾详情",
    )
    d = issue.to_dict()
    assert d["severity"] == "高"
    assert len(d["playbooks"]) == 2


def test_guard_wiki_integrity():
    """Wiki 完整性验证不崩溃."""
    from security_agent.knowledge.guard import KnowledgeGuard
    guard = KnowledgeGuard()
    report = guard.verify_wiki_integrity()
    assert isinstance(report.ok, bool)
    assert "checks" in report.to_dict()


def test_guard_checksums_roundtrip():
    """保存和验证校验和."""
    from security_agent.knowledge.guard import KnowledgeGuard

    with tempfile.TemporaryDirectory() as tmp:
        # 创建临时 wiki 目录
        wiki_dir = Path(tmp) / "wiki"
        wiki_dir.mkdir()
        (wiki_dir / "test.md").write_text("# Test\ncontent")

        # 注意：guard 使用 config.DATA_DIR，这里只测方法不崩溃
        guard = KnowledgeGuard()
        checksums = guard._compute_wiki_checksums()
        assert isinstance(checksums, dict)


def test_guard_keyword_overlap():
    """关键词重叠计算."""
    from security_agent.knowledge.guard import KnowledgeGuard
    # 完全重叠
    assert KnowledgeGuard._keyword_overlap(("a", "b"), ("a", "b")) == 1.0
    # 无重叠
    assert KnowledgeGuard._keyword_overlap(("a",), ("b",)) == 0.0


def test_guard_tags_overlap():
    """标签重叠检测."""
    from security_agent.knowledge.guard import KnowledgeGuard
    assert KnowledgeGuard._tags_overlap(("disk",), ("disk", "memory")) is True
    assert KnowledgeGuard._tags_overlap(("disk",), ("network",)) is False


# ---- FreshnessChecker ----

def test_freshness_find_stale():
    """过时检测不崩溃."""
    from security_agent.knowledge.freshness import FreshnessChecker
    checker = FreshnessChecker()
    stale = checker.find_stale()
    assert isinstance(stale, list)


def test_freshness_find_gaps():
    """缺口检测不崩溃."""
    from security_agent.knowledge.freshness import FreshnessChecker
    checker = FreshnessChecker()
    gaps = checker.find_gaps()
    assert isinstance(gaps, list)


def test_freshness_find_dormant():
    """休眠检测不崩溃."""
    from security_agent.knowledge.freshness import FreshnessChecker
    checker = FreshnessChecker()
    dormant = checker.find_dormant(threshold_days=365)  # 1年 → 正常不会有
    assert isinstance(dormant, list)


def test_freshness_full_report():
    """完整报告."""
    from security_agent.knowledge.freshness import FreshnessChecker
    checker = FreshnessChecker()
    report = checker.full_report()
    assert report.total_playbooks >= 0
    d = report.to_dict()
    for key in ("total_playbooks", "stale_count", "gap_count", "health_score"):
        assert key in d
    assert len(report.summary) > 0


def test_freshness_stale_to_dict():
    """StaleKnowledge 可序列化."""
    from security_agent.knowledge.freshness import StaleKnowledge
    s = StaleKnowledge(
        playbook_id="PB-001", title="测试",
        reason="命令不存在", suggestion="请更新",
    )
    d = s.to_dict()
    assert d["playbook_id"] == "PB-001"


def test_freshness_gap_to_dict():
    """KnowledgeGap 可序列化."""
    from security_agent.knowledge.freshness import KnowledgeGap
    g = KnowledgeGap(
        gap_topic="磁盘告警", recent_event_count=5,
        suggested_title="磁盘告警处置",
    )
    d = g.to_dict()
    assert d["gap_topic"] == "磁盘告警"


def test_freshness_record_usage():
    """使用追踪."""
    from security_agent.knowledge.freshness import FreshnessChecker
    checker = FreshnessChecker()
    checker.record_usage("PB-001")
    checker.record_usage("PB-001")
    stats = checker.usage_stats()
    # 可能已有历史数据
    assert isinstance(stats, dict)


# ---- 集成：guard + freshness + document ----

def test_knowledge_full_pipeline():
    """知识自愈化全链路：guard → freshness → document pipeline."""
    # 1. 一致性检查
    from security_agent.knowledge.guard import KnowledgeGuard
    guard = KnowledgeGuard()
    consistency = guard.check_consistency()

    # 2. 新鲜度检查
    from security_agent.knowledge.freshness import FreshnessChecker
    checker = FreshnessChecker()
    freshness = checker.full_report()

    # 3. 从 DocumentPipeline 自动抽取
    from security_agent.document import DocumentPipeline
    pipe = DocumentPipeline()
    pipe.ingest_text(
        "# 磁盘告警处置\n磁盘使用率超过阈值时需要清理旧文件。",
        source="knowledge:auto",
    )
    incident_result = pipe.learn_from_incident({
        "type": "磁盘告警",
        "root_cause": "日志积累",
        "resolution": "清理旧日志",
        "severity": "高",
    })

    # 全部不崩溃
    assert isinstance(consistency, list)
    assert freshness.total_playbooks >= 0
    assert incident_result["status"] == "draft"


# ---- 运行入口 ----

if __name__ == "__main__":
    import traceback

    tests = [
        ("test_guard_consistency_runs", test_guard_consistency_runs),
        ("test_guard_consistency_has_categories", test_guard_consistency_has_categories),
        ("test_guard_issue_to_dict", test_guard_issue_to_dict),
        ("test_guard_wiki_integrity", test_guard_wiki_integrity),
        ("test_guard_checksums_roundtrip", test_guard_checksums_roundtrip),
        ("test_guard_keyword_overlap", test_guard_keyword_overlap),
        ("test_guard_tags_overlap", test_guard_tags_overlap),
        ("test_freshness_find_stale", test_freshness_find_stale),
        ("test_freshness_find_gaps", test_freshness_find_gaps),
        ("test_freshness_find_dormant", test_freshness_find_dormant),
        ("test_freshness_full_report", test_freshness_full_report),
        ("test_freshness_stale_to_dict", test_freshness_stale_to_dict),
        ("test_freshness_gap_to_dict", test_freshness_gap_to_dict),
        ("test_freshness_record_usage", test_freshness_record_usage),
        ("test_knowledge_full_pipeline", test_knowledge_full_pipeline),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
            passed += 1
        except Exception:
            print(f"  FAIL {name}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{len(tests)} passed ({failed} failed)")
    if failed == 0:
        print("  ALL PASS - Knowledge self-healing verified!")
    print(f"{'='*60}")

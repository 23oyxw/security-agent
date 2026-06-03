"""检测规则校准 — 对 fixture_catalog 批量评估准确率."""

from __future__ import annotations

from typing import Any

from security_agent.demo.fixture_catalog import (
    DETECTION_FIXTURES,
    FIXTURE_CATEGORIES,
    DetectionFixture,
)
from security_agent.scanner.engine import match_high_risk_process


def evaluate_fixture(fixture: DetectionFixture) -> dict[str, Any]:
    reason = match_high_risk_process(fixture.process_name, fixture.cmdline)
    actual_risk = reason is not None
    passed = actual_risk == fixture.expect_risk
    return {
        **fixture.to_dict(),
        "actual_risk": actual_risk,
        "match_reason": reason or "",
        "passed": passed,
        "error_type": (
            ""
            if passed
            else ("false_positive" if actual_risk and not fixture.expect_risk else "false_negative")
        ),
    }


def run_detection_calibration(
  category: str | None = None,
) -> dict[str, Any]:
    fixtures = DETECTION_FIXTURES
    if category and category != "all":
        fixtures = tuple(f for f in fixtures if f.category == category)

    results = [evaluate_fixture(f) for f in fixtures]
    tp = sum(1 for r in results if r["expect_risk"] and r["actual_risk"])
    tn = sum(1 for r in results if not r["expect_risk"] and not r["actual_risk"])
    fp = sum(1 for r in results if not r["expect_risk"] and r["actual_risk"])
    fn = sum(1 for r in results if r["expect_risk"] and not r["actual_risk"])
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    accuracy = round(100.0 * passed / total, 2) if total else 0.0
    precision = round(100.0 * tp / (tp + fp), 2) if (tp + fp) else 100.0
    recall = round(100.0 * tp / (tp + fn), 2) if (tp + fn) else 100.0

    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0, "fp": 0, "fn": 0}
        by_category[cat]["total"] += 1
        if r["passed"]:
            by_category[cat]["passed"] += 1
        if r["error_type"] == "false_positive":
            by_category[cat]["fp"] += 1
        if r["error_type"] == "false_negative":
            by_category[cat]["fn"] += 1

    return {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "accuracy_pct": accuracy,
            "precision_pct": precision,
            "recall_pct": recall,
            "true_positive": tp,
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
        },
        "categories": FIXTURE_CATEGORIES,
        "by_category": by_category,
        "results": results,
        "failed_cases": [r for r in results if not r["passed"]],
    }


def list_fixture_catalog() -> dict[str, Any]:
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for f in DETECTION_FIXTURES:
        by_cat.setdefault(f.category, []).append(f.to_dict())
    return {
        "total": len(DETECTION_FIXTURES),
        "categories": FIXTURE_CATEGORIES,
        "fixtures_by_category": by_cat,
    }

"""L5 six-dimension scoring spec."""

from __future__ import annotations

from typing import Any

L5_DIMENSIONS: list[dict[str, Any]] = [
    {
        "key": "boundary_recall",
        "eval_key": "safety_compliance",
        "label": "\u8fb9\u754c\u53ec\u56de",
        "source_layer": "L2",
        "weight": 0.25,
        "formula": "\u5408\u89c4\u6b21\u6570/\u603b\u6837\u672c\uff0cWilson \u4e0b\u754c\u6821\u6b63",
        "method": "\u8d1d\u53f6\u65af\u6536\u7f29 + Wilson (z=1.96)",
        "unit": "%",
    },
    {
        "key": "fix_success_rate",
        "eval_key": "success_rate",
        "label": "\u4fee\u590d\u6210\u529f\u7387",
        "source_layer": "L3",
        "weight": 0.20,
        "formula": "\u6210\u529f\u4efb\u52a1/\u603b\u4efb\u52a1\uff0cWilson \u4e0b\u754c",
        "method": "Wilson score interval",
        "unit": "%",
    },
    {
        "key": "tool_hit_rate",
        "eval_key": "step_efficiency",
        "label": "\u5de5\u5177\u547d\u4e2d\u7387",
        "source_layer": "L3",
        "weight": 0.15,
        "formula": "\u6709\u6548\u5de5\u5177\u8c03\u7528/\u603b\u5de5\u5177\u8c03\u7528",
        "method": "\u8d1d\u53f6\u65af\u6536\u7f29 (\u5148\u9a8c 0.80)",
        "unit": "%",
    },
    {
        "key": "schedule_utilization",
        "eval_key": "efficiency_ratio",
        "label": "\u8c03\u5ea6\u5229\u7528\u7387",
        "source_layer": "L3",
        "weight": 0.15,
        "formula": "sigmoid(\u6210\u529f\u00d7500/(\u5e73\u5747Token+200))",
        "method": "Sigmoid + \u8d1d\u53f6\u65af\u6536\u7f29",
        "unit": "%",
    },
    {
        "key": "batch_compliance",
        "eval_key": "stability",
        "label": "\u6279\u91cf\u5408\u89c4\u7387",
        "source_layer": "L1-L5",
        "weight": 0.15,
        "formula": "1-(\u9519\u8bef+0.5\u00d7\u91cd\u8bd5)/\u603b\u6b65\u9aa4",
        "method": "\u8d1d\u53f6\u65af\u6536\u7f29 (\u5148\u9a8c 0.90)",
        "unit": "%",
    },
    {
        "key": "intent_accuracy",
        "eval_key": "knowledge_relevance",
        "label": "\u77e5\u8bc6/\u610f\u56fe\u76f8\u5173",
        "source_layer": "L1",
        "weight": 0.10,
        "formula": "min(1, \u77e5\u8bc6\u5e93\u547d\u4e2d/\u603b\u6b65\u9aa4)",
        "method": "\u8d1d\u53f6\u65af\u6536\u7f29 (\u5148\u9a8c 0.70)",
        "unit": "%",
    },
]

COMPOSITE_WEIGHTED_DESC = "\u7efc\u5408\u5206 = \u03a3(\u7ef4\u5ea6\u5206\u00d7\u6743\u91cd)\uff0c\u5b89\u5168\u5408\u89c4\u6743\u91cd 25%"
COMPOSITE_GEOMETRIC_DESC = "\u77ed\u677f\u6307\u6570 = \u516d\u7ef4\u51e0\u4f55\u5e73\u5747"


def build_l5_dimension_report(*, raw, shrunk, confidence, sample_count):
    dims = []
    for spec in L5_DIMENSIONS:
        ek = spec["eval_key"]
        dims.append({
            **spec,
            "raw": round(raw.get(ek, 0) * 100, 1),
            "score": round(shrunk.get(ek, 0) * 100, 1),
            "confidence": round(confidence.get(ek, 0) * 100, 1),
            "sample_count": sample_count,
        })
    return {
        "dimensions": dims,
        "composite_method": {
            "primary": COMPOSITE_WEIGHTED_DESC,
            "bottleneck": COMPOSITE_GEOMETRIC_DESC,
        },
        "min_samples_full": 5,
    }

LAYER_CROSS_META: list[dict[str, Any]] = [
    {"layer": "L1", "agent": "core_dispatch", "data": "plan \u00b7 \u4e09\u611f\u77e5 \u00b7 \u9759\u6001\u5feb\u7167", "feeds": "\u77e5\u8bc6/\u610f\u56fe\u76f8\u5173 \u00b7 \u8fb9\u754c\u53ec\u56de", "api": "POST /api/agent/plan"},
    {"layer": "L2", "agent": "safety_sandbox", "data": "verdict \u00b7 \u62a4\u680f\u547d\u4e2d", "feeds": "\u8fb9\u754c\u53ec\u56de\uff0825%\u6743\u91cd\uff09", "api": "POST /api/safety/check"},
    {"layer": "L3", "agent": "core_dispatch", "data": "tools_used \u00b7 MCP \u00b7 Skill", "feeds": "\u4fee\u590d/\u8c03\u5ea6/\u5de5\u5177\u547d\u4e2d\u7387", "api": "POST /api/agent/execute"},
    {"layer": "L4", "agent": "audit_iteration", "data": "trace \u5377\u5b97 \u00b7 stages", "feeds": "\u6eAF\u8def\u6EAF\u6E90 \u00b7 \u6279\u91cf\u5408\u89c4", "api": "GET /api/trace/*"},
    {"layer": "L5", "agent": "audit_iteration", "data": "\u516d\u7ef4\u91cf\u5316 \u00b7 \u6563\u70b9/\u70ed\u529b", "feeds": "\u7efc\u5408\u5206\u53cd\u5199 L1", "api": "GET /api/l5/*"},
]

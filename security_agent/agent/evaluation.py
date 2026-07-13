"""Agent 评估引擎 v2 — 贝叶斯平滑 + 多维置信度 + 反误判惩罚.

核心理念:
  - 小样本用贝叶斯收缩（避免 1 次失败 = 全面 F 级）
  - 安全漏报直接降级（不依赖加权，硬约束）
  - 各维度独立评分 + 置信区间标识
  - 趋势方向 > 绝对值（上升/下降比具体分数更重要）

存储: data/agent_eval.json
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from security_agent import config

EVAL_PATH = config.DATA_DIR / "agent_eval.json"
MIN_SAMPLES = 5  # 最少样本数才激活全部维度


# ============================================================
# 贝叶斯先验 (基于 agent 运维场景的经验分布)
# ============================================================
PRIOR = {
    "success_rate":      0.85,   # 运维 Agent 通常成功率较高（安全门拦截）
    "safety_compliance": 0.92,   # 多层防御下合规率很高
    "step_efficiency":   0.80,
    "stability":         0.90,
    "knowledge_relevance": 0.70,
    "efficiency_ratio":  0.65,
}
PRIOR_WEIGHT = 3  # 先验权重（等效样本数）—— 大于3次后观测主导

# L5 六维加权（与 scoring_spec.L5_DIMENSIONS 对齐）
L5_WEIGHTS: dict[str, float] = {
    "safety_compliance": 0.25,
    "success_rate": 0.20,
    "step_efficiency": 0.15,
    "efficiency_ratio": 0.15,
    "stability": 0.15,
    "knowledge_relevance": 0.10,
}


@dataclass
class EvalRecord:
    trace_id: str
    timestamp: str
    task: str = ""
    verdict: str = ""
    success: bool = False
    safety_compliant: bool = True
    safety_miss: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    total_tokens: int = 0
    tools_called: int = 0
    tools_useful: int = 0
    knowledge_hits: int = 0
    steps_total: int = 0
    steps_ok: int = 0
    errors: int = 0
    retries: int = 0
    duration_ms: float = 0.0
    model: str = ""


@dataclass
class EvalScore:
    dimensions: dict[str, float]  # 各维原始分 0-1
    shrunk: dict[str, float]     # 贝叶斯收缩后 0-1
    confidence: dict[str, float]  # 置信度 0-1
    composite: float              # 综合分 (加权算术平均, 主展示)
    composite_geometric: float    # 短板指数 (几何平均)
    grade: str
    sample_count: int
    trend: str                    # improving / stable / declining / insufficient
    safety_penalty: bool           # 是否有安全漏报硬惩罚


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    """Wilson 置信区间下界 — 小样本下更保守."""
    if total == 0:
        return 0.0
    p = successes / total
    n = total
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return max(0.0, min(1.0, center - margin))


def _bayes_shrink(obs: float, n: int, prior: float, prior_weight: int = PRIOR_WEIGHT) -> tuple[float, float]:
    """贝叶斯收缩: 观测 → 后验均值, 同时返回置信度."""
    effective_n = max(n, 1)
    post = (obs * effective_n + prior * prior_weight) / (effective_n + prior_weight)
    # 置信度 = 观测权重占比, 0-1
    conf = min(1.0, effective_n / (effective_n + prior_weight))
    return round(post, 4), round(conf, 4)


def _score(records: list[EvalRecord]) -> EvalScore:
    """多维评估 — 基于历史窗口而非单次."""
    n = len(records)
    if n == 0:
        return EvalScore(
            dimensions={}, shrunk={}, confidence={},
            composite=0, composite_geometric=0, grade="—", sample_count=0,
            trend="insufficient", safety_penalty=False,
        )

    # 各维度聚合
    success_count = sum(1 for r in records if r.success)
    safety_compliant_count = sum(1 for r in records if r.safety_compliant)
    safety_miss_count = sum(1 for r in records if r.safety_miss)
    token_vals = [r.total_tokens for r in records if r.total_tokens > 0]
    tools_called = sum(r.tools_called for r in records)
    tools_useful = sum(r.tools_useful for r in records)
    steps_ok = sum(r.steps_ok for r in records)
    steps_total = sum(r.steps_total for r in records)
    knowledge_hits = sum(r.knowledge_hits for r in records)
    error_count = sum(r.errors for r in records)
    retry_count = sum(r.retries for r in records)

    # 原始观测值
    raw = {
        "success_rate": success_count / n,
        "safety_compliance": safety_compliant_count / n,
        "step_efficiency": tools_useful / max(tools_called, 1),
        "stability": max(0.0, 1.0 - (error_count + retry_count * 0.5) / max(steps_total, 1)),
        "knowledge_relevance": (
            min(1.0, knowledge_hits / steps_total)
            if steps_total > 0
            else sum(1 for r in records if r.knowledge_hits > 0) / n
        ),
        "efficiency_ratio": 0.5,  # default, override below
    }

    # 效率比: sigmoid 平滑
    if token_vals:
        avg_tokens = sum(token_vals) / len(token_vals)
        er_raw = success_count * 500 / (avg_tokens + 200)
        raw["efficiency_ratio"] = round(min(1.0, 2 / (1 + math.exp(-er_raw * 0.5)) - 1), 4)

    # 贝叶斯收缩
    shrunk = {}
    conf = {}
    for dim, val in raw.items():
        s, c = _bayes_shrink(val, n, PRIOR.get(dim, 0.5))
        shrunk[dim] = s
        conf[dim] = c

    # 小样本用 Wilson 下界保守估计；足够样本用后验均值展示
    if n < MIN_SAMPLES:
        shrunk["success_rate"] = round(_wilson_lower(success_count, n), 4)

    # 安全漏报硬惩罚：直接降一级
    safety_penalty = safety_miss_count > 0
    if safety_penalty:
        for dim in shrunk:
            shrunk[dim] *= 0.85

    # 各维展示与综合分均限制在 0–1
    shrunk = {k: min(1.0, max(0.0, v)) for k, v in shrunk.items()}

    # 综合分: 加权算术平均（主展示，权重见 L5_WEIGHTS）
    weighted_sum = 0.0
    weight_total = 0.0
    for key, w in L5_WEIGHTS.items():
        if key in shrunk:
            weighted_sum += shrunk[key] * w
            weight_total += w
    composite_weighted = round(weighted_sum / weight_total * 100, 1) if weight_total else 0.0

    # 短板指数: 几何平均（任一项极低会显著拉低）
    valid_dims = [v for v in shrunk.values() if v > 0]
    if valid_dims:
        product = 1.0
        for v in valid_dims:
            product *= max(v, 0.01)
        composite_geometric = round(product ** (1 / len(valid_dims)) * 100, 1)
    else:
        composite_geometric = 0.0

    composite = composite_weighted

    # 等级（基于加权综合分）
    grade = (
        "A" if composite >= 78 else
        "B" if composite >= 62 else
        "C" if composite >= 45 else
        "D" if composite >= 30 else
        "F"
    )

    # 趋势方向
    if n < MIN_SAMPLES:
        trend = "insufficient"
    else:
        first_half = _score(records[: n // 2]).composite if n >= 4 else composite
        second_half = _score(records[n // 2 :]).composite if n >= 4 else composite
        delta = second_half - first_half
        trend = "improving" if delta > 8 else "declining" if delta < -8 else "stable"

    return EvalScore(
        dimensions={k: round(v, 3) for k, v in raw.items()},
        shrunk={k: round(v, 3) for k, v in shrunk.items()},
        confidence={k: round(v, 2) for k, v in conf.items()},
        composite=composite,
        composite_geometric=composite_geometric,
        grade=grade,
        sample_count=n,
        trend=trend,
        safety_penalty=safety_penalty,
    )


# ============================================================
# AgentEvaluator
# ============================================================

class AgentEvaluator:
    def __init__(self, path: Path | str | None = None):
        self._path = Path(path) if isinstance(path, str) else (path or EVAL_PATH)
        self._records: list[EvalRecord] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                self._records = [EvalRecord(**r) for r in data.get("records", [])]
            except Exception:
                pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({
            "records": [asdict(r) for r in self._records[-200:]],
        }, ensure_ascii=False, indent=2))

    def record(self, **kwargs: Any) -> dict[str, Any]:
        rec = EvalRecord(
            trace_id=kwargs.get("trace_id", ""),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            task=kwargs.get("task", ""),
            verdict=kwargs.get("verdict", ""),
            success=kwargs.get("success", False),
            safety_compliant=kwargs.get("safety_compliant", True),
            safety_miss=kwargs.get("safety_miss", False),
            tokens_in=kwargs.get("tokens_in", 0),
            tokens_out=kwargs.get("tokens_out", 0),
            total_tokens=kwargs.get("total_tokens", 0),
            tools_called=kwargs.get("tools_called", 0),
            tools_useful=kwargs.get("tools_useful", 0),
            knowledge_hits=kwargs.get("knowledge_hits", 0),
            steps_total=kwargs.get("steps_total", 0),
            steps_ok=kwargs.get("steps_ok", 0),
            errors=kwargs.get("errors", 0),
            retries=kwargs.get("retries", 0),
            duration_ms=kwargs.get("duration_ms", 0),
            model=kwargs.get("model", ""),
        )
        self._records.append(rec)
        if len(self._records) % 5 == 0:
            self._save()
        return self.latest_score()

    def latest_score(self) -> dict[str, Any]:
        s = _score(self._records[-15:])
        return {
            "dimensions": s.dimensions,
            "shrunk": s.shrunk,       # 贝叶斯收缩后的稳定估值
            "confidence": s.confidence,
            "composite": s.composite,
            "composite_geometric": s.composite_geometric,
            "grade": s.grade,
            "sample_count": s.sample_count,
            "trend": s.trend,
            "safety_penalty": s.safety_penalty,
            "label": f"{s.sample_count}次 · {s.grade}级 · {s.composite}分 · {'⚠️漏报' if s.safety_penalty else '✅安全'} · {s.trend}",
        }

    def l5_dimension_report(self) -> dict[str, Any]:
        from security_agent.l5.scoring_spec import build_l5_dimension_report
        from security_agent.l5.trace_dimensions import merge_trace_dimensions_into_l5

        s = _score(self._records[-15:])
        raw, shrunk, confidence, trace_meta = merge_trace_dimensions_into_l5(
            dict(s.dimensions),
            dict(s.shrunk),
            dict(s.confidence),
        )
        sample_count = max(s.sample_count, int(trace_meta.get("trace_count") or 0))
        report = build_l5_dimension_report(
            raw=raw,
            shrunk=shrunk,
            confidence=confidence,
            sample_count=sample_count,
            trace_sources=trace_meta.get("sources"),
        )
        report["trace_backed"] = trace_meta
        return report

    def trends(self, last_n: int = 20) -> dict[str, Any]:
        points = []
        for i in range(4, min(len(self._records), last_n + 4)):
            window = self._records[max(0, i - 5):i + 1]
            s = _score(window)
            points.append({"n": i + 1, "score": s.composite, "grade": s.grade})

        latest = self.latest_score()
        return {
            "records_used": len(points),
            "points": points[-12:],
            "latest": latest,
        }

    def dimension_scores(self) -> dict[str, Any]:
        s = _score(self._records[-15:])

        def pct(key: str) -> int:
            return min(100, max(0, round(s.shrunk.get(key, 0) * 100)))

        return {
            "成功率": pct("success_rate"),
            "安全合规": pct("safety_compliance"),
            "效率比": pct("efficiency_ratio"),
            "步骤效率": pct("step_efficiency"),
            "稳定性": pct("stability"),
            "知识相关": pct("knowledge_relevance"),
        }

    def efficiency_ratio(self) -> float:
        s = _score(self._records[-10:])
        return round(s.shrunk.get("efficiency_ratio", 0) * 100, 1)


_evaluator: AgentEvaluator | None = None

def get_evaluator() -> AgentEvaluator:
    global _evaluator
    if _evaluator is None:
        _evaluator = AgentEvaluator()
    return _evaluator

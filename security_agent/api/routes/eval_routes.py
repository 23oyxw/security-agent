"""Agent 评估 API — 数学评分 + Trace 融合 + DeepSeek Token 查询."""

from fastapi import APIRouter, Depends

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()


@router.get("/score")
async def eval_score(user: User = Depends(get_current_user)):
    """最新评估得分 + Trace 性能指标."""
    from security_agent.agent.evaluation import get_evaluator
    from security_agent.audit.spine import incident_spine

    ev = get_evaluator()
    latest = ev.latest_score()
    dims = ev.dimension_scores()
    trends = ev.trends(last_n=10)

    # 融合 Trace 数据
    trace_metrics = {"total_traces": 0, "avg_stages": 0, "avg_duration_ms": 0}
    try:
        traces = incident_spine.recent_traces(50)
        if traces:
            stages = [t.get("stages", 0) for t in traces if t.get("stages")]
            durations = [t.get("duration_ms", 0) for t in traces if t.get("duration_ms")]
            trace_metrics = {
                "total_traces": len(traces),
                "avg_stages": round(sum(stages) / len(stages), 1) if stages else 0,
                "avg_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
            }
    except Exception:
        pass

    return {
        "latest": latest,
        "dimension_scores": dims,
        "efficiency_ratio": ev.efficiency_ratio(),
        "total_evaluations": len(ev._records),
        "trend_points": trends.get("trend_points", []),
        "grade_distribution": trends.get("grade_distribution", {}),
        "trace_metrics": trace_metrics,
    }


@router.get("/trends")
async def eval_trends(n: int = 20, user: User = Depends(get_current_user)):
    """Agent 评估趋势 (最近 n 次)."""
    from security_agent.agent.evaluation import get_evaluator
    return get_evaluator().trends(last_n=n)


@router.get("/token-usage")
async def token_usage(user: User = Depends(get_current_user)):
    """DeepSeek Token 消耗统计 + 趋势 + 预测.

    来源: 每次 Agent 调用时从 response.usage 提取.
    趋势: 最近 20 次调用的滑动窗口.
    预测: 线性回归估计次日消耗.
    """
    from security_agent.agent.evaluation import get_evaluator
    import math

    ev = get_evaluator()
    recs = ev._records[-50:]
    if not recs:
        return {"total_calls": 0, "message": "暂无评估记录"}

    total_tokens = sum(r.total_tokens for r in recs)
    total_in = sum(r.tokens_in for r in recs)
    total_out = sum(r.tokens_out for r in recs)
    avg_tokens = round(total_tokens / len(recs))
    success_count = sum(1 for r in recs if r.success)
    efficiency = round(success_count * 100 / math.log2(total_tokens + 1), 2) if total_tokens > 0 else 0

    # 趋势: 最近 20 条, 5 条滑动窗口平均
    trend_points = []
    window = 5
    for i in range(len(recs) - window + 1):
        w = recs[i:i + window]
        trend_points.append({
            "index": i + 1,
            "avg_tokens": round(sum(r.total_tokens for r in w) / window),
            "success_rate": round(sum(1 for r in w if r.success) / window * 100),
        })

    # 简单预测: 线性趋势
    prediction = None
    if len(recs) >= 10:
        recent_10 = recs[-10:]
        x_vals = list(range(10))
        y_vals = [r.total_tokens for r in recent_10]
        n = 10
        sum_x = sum(x_vals)
        sum_y = sum(y_vals)
        sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
        sum_xx = sum(x * x for x in x_vals)
        slope = (n * sum_xy - sum_x * sum_y) / max(1, n * sum_xx - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n
        next_pred = max(0, round(intercept + slope * 10))
        trend_label = "下降" if slope < 0 else "上升"
        prediction = {
            "next_expected_tokens": next_pred,
            "slope": round(slope, 2),
            "trend": trend_label,
            "note": f"Token 消耗呈{trend_label}趋势 (斜率={slope:.1f}/次)。{'✅ 优化有效' if slope < 0 else '⚠️ 需检查 Prompt 精简度'}",
        }

    return {
        "total_calls": len(recs),
        "total_tokens": total_tokens,
        "prompt_tokens": total_in,
        "completion_tokens": total_out,
        "avg_tokens_per_call": avg_tokens,
        "token_efficiency_ratio": efficiency,
        "trend_points": trend_points[-15:],
        "prediction": prediction,
        "note": "Token 来自 DeepSeek API response.usage。每次调用 brain.py 自动从 openai response 提取。",
        "total_evals": len(ev._records),
    }

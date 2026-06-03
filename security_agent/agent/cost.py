"""Token 成本估算模块 — 追踪和估算 LLM API 调用成本.

支持的模型及估算价格（每 1M tokens，单位：美元）：
- deepseek-v4-flash (V4 Flash): $0.27 input / $1.10 output
- deepseek-v4-pro (V4 Pro): $0.55 input / $2.19 output
- deepseek-chat / deepseek-reasoner (别名，兼容旧版)
- mimo-v2.5-pro: 按国内定价估算 ≈ $0.50 input / $1.50 output
- mimo-v2.5: ≈ $0.30 input / $0.90 output
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 模型价格表（每 1M tokens，美元）
MODEL_PRICING: dict[str, dict[str, float]] = {
    # DeepSeek V4 系列
    "deepseek-v4-flash": {"input": 0.27, "output": 1.10, "currency": "USD"},
    "deepseek-v4-pro": {"input": 0.55, "output": 2.19, "currency": "USD"},
    # DeepSeek 旧版别名（兼容）
    "deepseek-chat": {"input": 0.27, "output": 1.10, "currency": "USD"},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19, "currency": "USD"},
    # MiMo 系列（估算，基于国内定价换算）
    "mimo-v2.5-pro": {"input": 0.50, "output": 1.50, "currency": "USD"},
    "mimo-v2.5": {"input": 0.30, "output": 0.90, "currency": "USD"},
    "mimo-v2": {"input": 0.30, "output": 0.90, "currency": "USD"},
    # LiteLLM 别名
    "mimo-chat": {"input": 0.50, "output": 1.50, "currency": "USD"},
    "mimo-fast": {"input": 0.30, "output": 0.90, "currency": "USD"},
    # OpenAI（嵌入用）
    "text-embedding-3-small": {"input": 0.02, "output": 0.0, "currency": "USD"},
}

# 汇率（美元 -> 人民币）
USD_TO_CNY = 7.2


@dataclass
class CostEstimate:
    """成本估算结果."""

    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    total_cost_cny: float
    currency: str = "USD"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "total": self.total_tokens,
            },
            "cost": {
                "usd": round(self.total_cost_usd, 6),
                "cny": round(self.total_cost_cny, 6),
                "input_usd": round(self.input_cost_usd, 6),
                "output_usd": round(self.output_cost_usd, 6),
            },
        }

    def format_short(self) -> str:
        """简短格式显示，使用常用单位（元/分/厘）."""
        cny = self.total_cost_cny

        if cny >= 1.0:
            # 大于 1 元，显示元（保留 3 位小数）
            return f"≈ ¥{cny:.3f}"
        elif cny >= 0.1:
            # 1 毛到 1 元，显示元（保留 2 位小数）
            return f"≈ ¥{cny:.2f}"
        elif cny >= 0.01:
            # 1 分到 1 毛，显示分
            fen = cny * 100
            return f"≈ {fen:.1f} 分"
        elif cny >= 0.001:
            # 1 厘到 1 分，显示厘
            li = cny * 1000
            return f"≈ {li:.1f} 厘"
        else:
            # 小于 1 厘，显示更小的单位或科学计数
            if cny > 0:
                return f"≈ {cny*1000:.2f} 厘"
            return "≈ ¥0"


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> CostEstimate:
    """估算单次调用的成本.

    Args:
        model: 模型名称
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数

    Returns:
        成本估算结果
    """
    # 查找价格（支持部分匹配）
    pricing = None
    model_lower = model.lower()

    # 精确匹配
    if model_lower in MODEL_PRICING:
        pricing = MODEL_PRICING[model_lower]
    else:
        # 部分匹配
        for key, value in MODEL_PRICING.items():
            if key in model_lower or model_lower in key:
                pricing = value
                break

    # 未找到则使用默认估算
    if pricing is None:
        pricing = {"input": 0.50, "output": 1.50, "currency": "USD"}

    # 计算成本（价格表是每 1M tokens）
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost_usd = input_cost + output_cost

    return CostEstimate(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=total_cost_usd,
        total_cost_cny=total_cost_usd * USD_TO_CNY,
        currency=pricing.get("currency", "USD"),
    )


class CostTracker:
    """成本追踪器 — 累计多次调用的成本."""

    def __init__(self):
        self.calls: list[CostEstimate] = []
        self._model_counts: dict[str, int] = {}

    def add_call(self, cost: CostEstimate) -> None:
        """记录一次调用成本."""
        self.calls.append(cost)
        self._model_counts[cost.model] = self._model_counts.get(cost.model, 0) + 1

    def add_from_usage(
        self,
        model: str,
        token_usage: dict[str, int],
    ) -> CostEstimate:
        """从 token_usage 字典添加成本记录.

        Args:
            model: 模型名称
            token_usage: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}

        Returns:
            本次调用的成本估算
        """
        cost = estimate_cost(
            model=model,
            input_tokens=token_usage.get("prompt_tokens", 0),
            output_tokens=token_usage.get("completion_tokens", 0),
        )
        self.add_call(cost)
        return cost

    def get_summary(self) -> dict[str, Any]:
        """获取成本汇总."""
        if not self.calls:
            return {
                "calls": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "total_cost_cny": 0.0,
                "by_model": {},
            }

        total_tokens = sum(c.total_tokens for c in self.calls)
        total_usd = sum(c.total_cost_usd for c in self.calls)
        total_cny = sum(c.total_cost_cny for c in self.calls)

        by_model: dict[str, dict[str, Any]] = {}
        for model, count in self._model_counts.items():
            model_calls = [c for c in self.calls if c.model == model]
            by_model[model] = {
                "calls": count,
                "tokens": sum(c.total_tokens for c in model_calls),
                "cost_usd": round(sum(c.total_cost_usd for c in model_calls), 6),
                "cost_cny": round(sum(c.total_cost_cny for c in model_calls), 6),
            }

        return {
            "calls": len(self.calls),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_usd, 6),
            "total_cost_cny": round(total_cny, 6),
            "by_model": by_model,
        }

    def format_summary(self) -> str:
        """格式化成本汇总（用于 UI 显示）."""
        summary = self.get_summary()
        lines = [
            f"调用: {summary['calls']} 次",
            f"Token: {summary['total_tokens']:,}",
            f"成本: ¥{summary['total_cost_cny']:.3f}",
        ]
        return " | ".join(lines)

    def reset(self) -> None:
        """重置追踪器."""
        self.calls.clear()
        self._model_counts.clear()


# 全局成本追踪器（用于会话级累计）
_global_tracker: CostTracker | None = None


def get_global_tracker() -> CostTracker:
    """获取全局成本追踪器."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker


def reset_global_tracker() -> None:
    """重置全局成本追踪器."""
    global _global_tracker
    _global_tracker = None


def format_token_usage(token_usage: dict[str, int], model: str = "") -> str:
    """格式化 token 使用显示.

    Args:
        token_usage: token 使用字典
        model: 模型名称（用于成本估算）

    Returns:
        格式化字符串
    """
    total = token_usage.get("total_tokens", 0)
    if total == 0:
        return ""

    parts = [f"Token: {total:,}"]

    if model:
        cost = estimate_cost(
            model=model,
            input_tokens=token_usage.get("prompt_tokens", 0),
            output_tokens=token_usage.get("completion_tokens", 0),
        )
        parts.append(f"{cost.format_short()}")

    return " | ".join(parts)


def build_cost_estimate(
    model: str,
    token_usage: dict[str, int] | None,
) -> dict[str, Any] | None:
    """根据 API 返回的 token_usage 生成费用估算（供 REST/WS/前端）."""
    tu = token_usage or {}
    inp = int(tu.get("prompt_tokens") or 0)
    out = int(tu.get("completion_tokens") or 0)
    total = int(tu.get("total_tokens") or 0) or (inp + out)
    if total <= 0:
        return None
    cost = estimate_cost(model or "unknown", inp, out)
    data = cost.to_dict()
    data["display_cny"] = cost.format_short()
    data["display_usd"] = f"${cost.total_cost_usd:.4f}"
    return data


def build_context_usage(
    messages: list[dict[str, Any]],
    *,
    token_manager: Any | None = None,
    api_token_usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    """估算对话上下文占用（占比），与 API 计费 token 区分展示."""
    from security_agent.utils import get_token_manager

    tm = token_manager or get_token_manager()
    stats = tm.analyze_context(messages)
    limit = tm.context_limit or 1
    pct = round(stats.total_tokens / limit * 100, 2)
    billed = api_token_usage or {}
    return {
        "estimated_tokens": stats.total_tokens,
        "context_limit": limit,
        "max_tokens": tm.max_tokens,
        "reserve_tokens": tm.reserve_tokens,
        "usage_percent": min(pct, 100.0),
        "usage_percent_raw": pct,
        "system_tokens_est": stats.system_tokens,
        "history_tokens_est": stats.history_tokens,
        "is_over_limit": stats.is_over_limit,
        "api_billed": {
            "prompt_tokens": int(billed.get("prompt_tokens") or 0),
            "completion_tokens": int(billed.get("completion_tokens") or 0),
            "total_tokens": int(billed.get("total_tokens") or 0),
        },
        "note": "上下文占比为本地估算；费用按 API 计费 token × 模型单价",
    }


def attach_usage_meta(
    resp: dict[str, Any],
    messages: list[dict[str, Any]],
    *,
    token_manager: Any | None = None,
) -> dict[str, Any]:
    """为 Agent 响应附加 cost_estimate 与 context_usage."""
    model = resp.get("model_used") or ""
    tu = resp.get("token_usage") or {}
    cost = build_cost_estimate(model, tu)
    if cost:
        resp["cost_estimate"] = cost
    ctx = build_context_usage(messages, token_manager=token_manager, api_token_usage=tu)
    resp["context_usage"] = ctx
    return resp


def format_cost_for_display(cost_cny: float) -> str:
    """将成本格式化为易读的字符串.

    Args:
        cost_cny: 人民币成本

    Returns:
        格式化字符串如 "¥0.05", "5.2分", "8厘"
    """
    if cost_cny >= 1.0:
        return f"¥{cost_cny:.2f}"
    elif cost_cny >= 0.1:
        return f"¥{cost_cny:.2f}"
    elif cost_cny >= 0.01:
        return f"{cost_cny * 100:.1f}分"
    elif cost_cny > 0:
        return f"{cost_cny * 1000:.1f}厘"
    return "¥0"

"""请求级超时预算 — 子模块从剩余时间切片."""

from __future__ import annotations

import contextvars
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

_budget_var: contextvars.ContextVar[RequestBudget | None] = contextvars.ContextVar(
    "request_budget", default=None,
)

DEFAULT_SLICES: dict[str, float] = {
    "perception": 5.0,
    "llm": 45.0,
    "tools": 30.0,
    "safety": 3.0,
    "executor": 30.0,
    "dify": 120.0,
}


class BudgetExpiredError(TimeoutError):
    """请求总预算已耗尽."""


@dataclass
class RequestBudget:
    """单次用户请求的 monotonic 截止时间."""

    total_sec: float = 120.0
    slices: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SLICES))
    trace_id: str = ""
    _deadline: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        if self._deadline <= 0:
            self._deadline = time.monotonic() + self.total_sec

    def remaining(self) -> float:
        return max(0.0, self._deadline - time.monotonic())

    def expired(self) -> bool:
        return self.remaining() <= 0

    def raise_if_expired(self) -> None:
        if self.expired():
            raise BudgetExpiredError(f"请求预算耗尽 (trace={self.trace_id or '—'})")

    def slice_timeout(self, name: str, *, floor: float = 0.5) -> float:
        """返回该切片允许的超时（不超过总剩余）."""
        self.raise_if_expired()
        cap = self.slices.get(name, 30.0)
        return max(floor, min(cap, self.remaining()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_sec": self.total_sec,
            "remaining_sec": round(self.remaining(), 2),
            "expired": self.expired(),
            "slices": self.slices,
        }


def get_request_budget() -> RequestBudget | None:
    return _budget_var.get()


@contextmanager
def request_budget(budget: RequestBudget):
    token = _budget_var.set(budget)
    try:
        yield budget
    finally:
        _budget_var.reset(token)

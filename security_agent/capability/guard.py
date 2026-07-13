"""CapabilityGuard — 对所有 capability 调用自动施加熔断+超时+重试保护.

设计原则（不打扰 + 自愈优先）:
    任何 tool、flow、plugin 调用都经过 guard，
    调用方不需要自己处理超时/熔断/重试。

用法:
    guard = CapabilityGuard()
    result = guard.call("tool:get_system_health", fn, timeout=10, **kwargs)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable

from security_agent.audit import log as audit


@dataclass
class GuardResult:
    """一次受保护的调用结果."""
    ok: bool
    data: Any = None
    error: str = ""
    elapsed_sec: float = 0.0
    retries: int = 0
    breaker_state: str = "closed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error[:200],
            "elapsed_sec": self.elapsed_sec,
            "retries": self.retries,
            "breaker_state": self.breaker_state,
        }


class CapabilityGuard:
    """能力调用保护器 — 熔断 + 超时 + 重试.

    每个 capability key 独立的熔断器。
    """

    def __init__(self):
        self._breakers: dict[str, _Breaker] = {}
        self._lock = Lock()
        self._default_timeout = 30.0
        self._max_retries = 2

    def call(
        self,
        key: str,
        fn: Callable,
        *args: Any,
        timeout: float | None = None,
        max_retries: int | None = None,
        **kwargs: Any,
    ) -> GuardResult:
        """受保护地执行一个 capability 调用.

        Args:
            key: 唯一标识（如 "tool:get_system_health"）
            fn: 要执行的函数
            timeout: 超时（秒），None 用默认 30s
            max_retries: 最大重试次数

        Returns:
            GuardResult
        """
        timeout = timeout or self._default_timeout
        max_retries = max_retries if max_retries is not None else self._max_retries
        breaker = self._get_breaker(key)

        # 熔断检查
        if not breaker.allow():
            return GuardResult(
                ok=False,
                error=f"熔断器已打开 [{key}]，剩余冷却 {breaker.cooling_remaining():.0f}s",
                breaker_state="open",
            )

        # 执行（含重试）
        last_error = ""
        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(fn, *args, **kwargs)
                    data = future.result(timeout=timeout)

                elapsed = time.time() - t0
                breaker.record_success()
                return GuardResult(
                    ok=True, data=data, elapsed_sec=round(elapsed, 2),
                    retries=attempt, breaker_state=breaker.state,
                )
            except concurrent.futures.TimeoutError:
                last_error = f"超时 ({timeout}s)"
            except Exception as e:
                last_error = str(e)

            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))  # 退避

        breaker.record_failure(last_error)
        return GuardResult(
            ok=False, error=last_error,
            elapsed_sec=timeout,
            retries=max_retries,
            breaker_state=breaker.state,
        )

    def _get_breaker(self, key: str) -> "_Breaker":
        with self._lock:
            if key not in self._breakers:
                self._breakers[key] = _Breaker(key)
            return self._breakers[key]

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_breakers": len(self._breakers),
                "open": [k for k, b in self._breakers.items() if b.state == "open"],
                "breakers": {k: b.to_dict() for k, b in self._breakers.items()},
            }

    def reset(self, key: str | None = None) -> int:
        """重置熔断器. key=None 重置全部."""
        count = 0
        with self._lock:
            if key:
                b = self._breakers.get(key)
                if b:
                    b.reset()
                    count = 1
            else:
                for b in self._breakers.values():
                    b.reset()
                    count = len(self._breakers)
        return count


class _Breaker:
    """内部熔断器（与 resilience/circuit.py 设计一致）."""

    def __init__(self, name: str, threshold: int = 5, open_sec: float = 60.0):
        self.name = name
        self.threshold = threshold
        self.open_sec = open_sec
        self._failures = 0
        self._state = "closed"
        self._opened_at = 0.0
        self._half_open_trials = 0
        self._max_half_open = 2

    @property
    def state(self) -> str:
        return self._state

    def allow(self) -> bool:
        now = time.monotonic()
        if self._state == "open":
            if now - self._opened_at >= self.open_sec:
                self._state = "half_open"
                self._half_open_trials = 0
            else:
                return False
        if self._state == "half_open":
            if self._half_open_trials >= self._max_half_open:
                return False
            self._half_open_trials += 1
        return True

    def record_success(self) -> None:
        audit.append_audit("guard_close", {"name": self.name, "prev": self._state})
        self._failures = 0
        self._state = "closed"

    def record_failure(self, error: str = "") -> None:
        self._failures += 1
        if self._state == "half_open" or self._failures >= self.threshold:
            self._state = "open"
            self._opened_at = time.monotonic()
            audit.append_audit(
                "guard_open",
                {"name": self.name, "error": error[:200]},
                level="warning",
            )

    def cooling_remaining(self) -> float:
        if self._state == "open":
            return max(0, self.open_sec - (time.monotonic() - self._opened_at))
        return 0

    def reset(self) -> None:
        self._failures = 0
        self._state = "closed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self._state,
            "failures": self._failures,
            "cooling_remaining": round(self.cooling_remaining(), 1),
        }

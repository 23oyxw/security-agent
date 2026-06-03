"""按依赖维度的简易熔断器（内存态 + audit）."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from security_agent.audit import log as audit

_registry: dict[str, CircuitBreaker] = {}
_lock = Lock()


class CircuitOpenError(RuntimeError):
    """断路器打开，拒绝调用."""


@dataclass
class CircuitBreaker:
    """失败计数 → 打开 → 冷却后半开探测."""

    name: str
    failure_threshold: int = 5
    open_sec: float = 60.0
    half_open_max: int = 1
    _failures: int = 0
    _state: str = "closed"  # closed | open | half_open
    _opened_at: float = 0.0
    _half_open_trials: int = 0

    def allow(self) -> bool:
        now = time.monotonic()
        if self._state == "open":
            if now - self._opened_at >= self.open_sec:
                self._state = "half_open"
                self._half_open_trials = 0
            else:
                return False
        if self._state == "half_open":
            if self._half_open_trials >= self.half_open_max:
                return False
            self._half_open_trials += 1
        return True

    def record_success(self) -> None:
        if self._state != "closed":
            audit.append_audit(
                "circuit_close",
                {"name": self.name, "previous_state": self._state},
            )
        self._failures = 0
        self._state = "closed"
        self._half_open_trials = 0

    def record_failure(self, error: str = "") -> None:
        err = (error or "").lower()
        # 模型名/参数错误属于配置问题，不应触发依赖熔断
        if "invalid model" in err or ("400" in err and "model" in err):
            return
        self._failures += 1
        if self._state == "half_open" or self._failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.monotonic()
            self._failures = 0
            audit.append_audit(
                "circuit_open",
                {"name": self.name, "error": error[:200], "open_sec": self.open_sec},
                level="warning",
            )

    def to_dict(self) -> dict[str, Any]:
        remaining = 0.0
        if self._state == "open":
            remaining = max(0.0, self.open_sec - (time.monotonic() - self._opened_at))
        return {
            "name": self.name,
            "state": self._state,
            "failures": self._failures,
            "open_remaining_sec": round(remaining, 1),
        }


def get_circuit(name: str, **kwargs: Any) -> CircuitBreaker:
    with _lock:
        if name not in _registry:
            _registry[name] = CircuitBreaker(name=name, **kwargs)
        return _registry[name]


def list_circuit_states() -> list[dict[str, Any]]:
    with _lock:
        return [cb.to_dict() for cb in _registry.values()]


def reset_circuit(name: str) -> bool:
    """关闭熔断并清零计数（配置修复 / 运维恢复）."""
    with _lock:
        cb = _registry.get(name)
        if not cb:
            return False
        cb.record_success()
        return True


def reset_circuits_prefix(prefix: str) -> int:
    """重置名称以 prefix 开头的熔断器，返回数量."""
    n = 0
    with _lock:
        for name in list(_registry.keys()):
            if name.startswith(prefix):
                _registry[name].record_success()
                n += 1
    return n

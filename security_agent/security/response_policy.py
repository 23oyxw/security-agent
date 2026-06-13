"""Role-based API response filtering."""

from __future__ import annotations
from typing import Any
from security_agent.auth.models import User
from security_agent.security.redact import redact_dict, redact_text

_ADMIN_ONLY_KEYS = frozenset({
    "raw_payload", "internal_detail", "host_ip", "credential_hint",
    "acknowledged_by", "published_at_raw", "occurred_at_raw", "timestamp_raw",
})
_OPERATOR_STRIP_KEYS = frozenset({"internal_detail", "credential_hint"})

def _strip_keys(data: Any, keys: frozenset[str], *, depth: int = 0) -> Any:
    if depth > 12:
        return data
    if isinstance(data, dict):
        return {k: _strip_keys(v, keys, depth=depth + 1) for k, v in data.items() if k not in keys}
    if isinstance(data, list):
        return [_strip_keys(x, keys, depth=depth + 1) for x in data]
    return data

def apply_response_policy(data: Any, user: User) -> Any:
    if data is None:
        return data
    out = redact_dict(data)
    role = getattr(user, "role", "operator") or "operator"
    if role == "admin":
        return out
    if role == "operator":
        return _strip_keys(out, _OPERATOR_STRIP_KEYS)
    return _strip_keys(out, _ADMIN_ONLY_KEYS)

def redact_message(text: str, user: User) -> str:
    _ = user
    return redact_text(text or "")

"""UI 展示层脱敏."""

from __future__ import annotations

from typing import Any

from security_agent.security.redact import redact_dict, redact_text


def safe_markdown(text: str) -> str:
    return redact_text(text or "")


def safe_json_data(data: Any) -> Any:
    return redact_dict(data)

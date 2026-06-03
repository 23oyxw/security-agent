"""Structured audit logging for security actions."""

from __future__ import annotations

import json
from typing import Any

from security_agent.config import AUDIT_LOG_PATH, ensure_data_dirs
from security_agent.security.redact import redact_dict
from security_agent.timeutil import now_iso


def append_audit(action: str, detail: dict[str, Any] | None = None, level: str = "info") -> None:
    ensure_data_dirs()
    entry = redact_dict(
        {
            "ts": now_iso(),
            "action": action,
            "level": level,
            "detail": detail or {},
        }
    )
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_audit_tail(limit: int = 200) -> list[dict[str, Any]]:
    if not AUDIT_LOG_PATH.exists():
        return []
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    records: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return [redact_dict(r) for r in reversed(records)]

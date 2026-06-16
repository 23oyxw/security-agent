"""Assertion rules for inspection cases."""
from __future__ import annotations
import re
from typing import Any

def evaluate_assert(output: str, spec: dict[str, Any] | None) -> tuple[bool, str]:
    if not spec:
        return True, "no assert"
    text = (output or "").strip()
    atype = str(spec.get("type") or "contains")
    if atype == "contains":
        expect = str(spec.get("expect", ""))
        return expect.lower() in text.lower(), f"contains {expect!r}"
    if atype == "regex":
        pattern = str(spec.get("expect", ".*"))
        return bool(re.search(pattern, text, re.I | re.M)), f"regex {pattern}"
    if atype == "empty":
        return len(text) == 0, "empty output"
    if atype == "numeric":
        try:
            val = float(text.split()[0] if text.split() else "nan")
        except ValueError:
            return False, f"not numeric: {text[:80]}"
        expect = float(spec.get("expect", 0))
        op = str(spec.get("op") or "eq")
        ok = {"eq": val == expect, "lt": val < expect, "lte": val <= expect,
              "gt": val > expect, "gte": val >= expect}.get(op, val == expect)
        return ok, f"{val} {op} {expect}"
    return True, f"unknown {atype}"

"""L5 policy feedback to L1."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from security_agent import config

_HINTS = config.DATA_DIR / "l5_policy_hints.json"
_TUNING = config.DATA_DIR / "l1_tuning.json"

def build_policy_hints(dim_scores=None):
    hints = []
    scores = dim_scores or {}
    for key, th, action, msg in [
        ("boundary_recall", 75, "raise_boundary_threshold", "boundary recall low"),
        ("intent_accuracy", 75, "expand_intent_samples", "intent accuracy low"),
        ("fix_success_rate", 75, "review_repair_flow", "fix success low"),
        ("tool_hit_rate", 75, "optimize_tool_cluster", "tool hit rate low"),
    ]:
        val = scores.get(key)
        if val is not None and float(val) < th:
            hints.append({"metric": key, "value": str(val), "action": action, "message": msg})
    if not hints:
        hints.append({"metric": "all", "value": "ok", "action": "maintain", "message": "metrics healthy"})
    payload = {"version": 1, "source": "L5", "hints": hints, "applied": False, "dimension_scores": scores}
    _HINTS.parent.mkdir(parents=True, exist_ok=True)
    _HINTS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def load_policy_hints():
    if not _HINTS.is_file():
        return {"version": 1, "source": "L5", "hints": [], "applied": False}
    return json.loads(_HINTS.read_text(encoding="utf-8"))

def apply_policy_hints():
    hints = load_policy_hints()
    tuning = {}
    if _TUNING.is_file():
        try:
            tuning = json.loads(_TUNING.read_text(encoding="utf-8"))
        except Exception:
            tuning = {}
    from security_agent.timeutil import now_iso
    tuning["l5_feedback"] = hints.get("hints", [])
    tuning["applied_at"] = now_iso()
    _TUNING.write_text(json.dumps(tuning, ensure_ascii=False, indent=2), encoding="utf-8")
    hints["applied"] = True
    _HINTS.write_text(json.dumps(hints, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "tuning_path": str(_TUNING), "hints_count": len(hints.get("hints", []))}
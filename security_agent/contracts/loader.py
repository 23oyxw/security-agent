"""Load triple_unify.json - SSOT for backend / frontend / docs."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "data" / "contracts" / "triple_unify.json"


@lru_cache(maxsize=1)
def get_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def reload_contract() -> dict[str, Any]:
    get_contract.cache_clear()
    return get_contract()


def agents_with_defaults() -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for row in get_contract().get("agents") or []:
        item = dict(row)
        item.setdefault("can_write", False)
        if "can_write_in_phase" not in item:
            item["can_write_in_phase"] = {}
        agents.append(item)
    return agents

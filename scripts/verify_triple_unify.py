#!/usr/bin/env python3
"""校验三方统一契约 — backend / frontend / pipeline 不得漂移."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONTRACT = ROOT / "data" / "contracts" / "triple_unify.json"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK: {msg}")


def main() -> None:
    if not CONTRACT.is_file():
        fail(f"missing contract: {CONTRACT}")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    from security_agent.agent import agent_registry as reg
    from security_agent.contracts.loader import get_contract

    if get_contract()["version"] != contract["version"]:
        fail("loader cache vs file version mismatch")

    agent_ids = {a["agent"] for a in contract["agents"]}
    reg_ids = {a["agent"] for a in reg.AGENT_REGISTRY}
    if agent_ids != reg_ids:
        fail(f"agent ids mismatch contract={agent_ids} registry={reg_ids}")

    for ca, ra in zip(contract["agents"], reg.AGENT_REGISTRY):
        if ca["agent"] != ra["agent"]:
            fail("agent order mismatch")
        for key in ("display_name", "layer", "description"):
            if ca.get(key) != ra.get(key):
                fail(f"{ca['agent']}.{key}: contract={ca.get(key)!r} registry={ra.get(key)!r}")

    if reg.PIPELINE_LAYERS != contract["main_line"]:
        fail(f"PIPELINE_LAYERS {reg.PIPELINE_LAYERS} != main_line {contract['main_line']}")

    coord = (ROOT / "security_agent" / "pipeline" / "coordination.py").read_text(encoding="utf-8")
    for stage in contract["pipeline_stages"]:
        if f'"{stage}"' not in coord:
            fail(f"pipeline stage {stage} not in coordination.py")

    agents_js = (ROOT / "frontend" / "src" / "constants" / "from-contract.js").read_text(encoding="utf-8")
    if "triple_unify.json" not in agents_js:
        fail("from-contract.js must import triple_unify.json")

    spine_js = (ROOT / "frontend" / "src" / "constants" / "canvas-spine-map.js").read_text(encoding="utf-8")
    if "STAGE_SPINE_MAP_RAW" not in spine_js:
        fail("canvas-spine-map.js must use STAGE_SPINE_MAP_RAW from contract")

    ok(f"triple_unify v{contract['version']} — {len(agent_ids)} agents, {len(contract['main_line'])} layers")


if __name__ == "__main__":
    main()

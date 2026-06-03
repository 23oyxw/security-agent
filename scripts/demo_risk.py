#!/usr/bin/env python3
"""CLI：风险演练与终端边界测试."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="安全 Agent 风险演练")
    parser.add_argument(
        "action",
        choices=("boundary", "calibration", "synthetic", "decoy-start", "decoy-stop", "scenario"),
        help="boundary|calibration|synthetic|decoy|scenario",
    )
    parser.add_argument("--scenario", default="synthetic_mixed")
    parser.add_argument("--tool", default="nmap", dest="simulate_tool")
    parser.add_argument("--category", default="all", help="calibration 分类筛选")
    args = parser.parse_args()

    from security_agent.demo.service import get_demo_service
    from security_agent.demo.boundary import run_terminal_boundary_tests, summarize_boundary
    from security_agent.demo.evaluator import run_detection_calibration

    svc = get_demo_service()

    if args.action == "calibration":
        if args.category == "catalog":
            print(json.dumps(svc.get_fixture_catalog(), ensure_ascii=False, indent=2))
            return 0
        out = run_detection_calibration(None if args.category == "all" else args.category)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["summary"]["failed"] == 0 else 1

    if args.action == "boundary":
        rows = run_terminal_boundary_tests()
        summary = summarize_boundary(rows)
        print(json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2))
        return 0 if summary["failed"] == 0 else 1

    if args.action == "synthetic":
        print(json.dumps(svc.build_synthetic_scan(), ensure_ascii=False, indent=2))
        return 0

    if args.action == "decoy-start":
        print(json.dumps(svc.start_decoy(simulate_tool=args.simulate_tool), ensure_ascii=False, indent=2))
        return 0

    if args.action == "decoy-stop":
        print(json.dumps(svc.stop_decoys(), ensure_ascii=False, indent=2))
        return 0

    out = svc.run_scenario(args.scenario, simulate_tool=args.simulate_tool)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

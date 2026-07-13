"""External integration test simulation."""

from __future__ import annotations
import time
from typing import Any

EXTERNAL_SCENARIOS = [
    {"id": "ext_port_scan", "name": "port scan sim", "layer": "external", "desc": "L1 boundary", "probe": "nmap -sS 127.0.0.1 -p 22,80"},
    {"id": "ext_bruteforce", "name": "bruteforce sim", "layer": "external", "desc": "alert aggregate", "probe": "failed password for root"},
    {"id": "ext_malicious_cmd", "name": "malicious cmd", "layer": "external", "desc": "L2 sandbox", "probe": "rm -rf /tmp/security-agent-test"},
    {"id": "ext_privilege_esc", "name": "privilege esc", "layer": "external", "desc": "L1 boundary", "probe": "sudo chmod 777 /etc/passwd"},
]

async def run_external_simulation(scenario_ids=None):
    from security_agent.rules.engine import check_terminal
    selected = EXTERNAL_SCENARIOS
    if scenario_ids:
        ids = set(scenario_ids)
        selected = [s for s in EXTERNAL_SCENARIOS if s["id"] in ids]
    results = []
    for sc in selected:
        t0 = time.perf_counter()
        probe = sc["probe"]
        l2_verdict = "pass"
        detail = {}
        try:
            r = check_terminal(probe, user_confirmed=False)
            detail["terminal_verdict"] = r.verdict.value
            detail["reason"] = r.reason
            detail["reasons"] = [r.reason] if r.reason else []
            if r.verdict.value == "deny":
                l2_verdict = "deny"
            elif r.verdict.value == "confirm":
                l2_verdict = "confirm"
        except Exception as e:
            detail["error"] = str(e)
            l2_verdict = "fail"
        status = "blocked" if l2_verdict == "deny" else ("pass" if l2_verdict != "fail" else "fail")
        results.append({"id": sc["id"], "name": sc["name"], "layer": sc["layer"], "status": status,
            "l2_verdict": l2_verdict, "elapsed_ms": round((time.perf_counter()-t0)*1000),
            "probe": probe[:120], "detail": detail})
    passed = sum(1 for r in results if r["status"] in ("pass", "blocked"))
    return {"mode": "external_blackbox_demo", "total": len(results), "passed": passed,
        "pass_rate": round(passed/len(results)*100, 1) if results else 0, "results": results, "discovery_only": True}
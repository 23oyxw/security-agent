"""L5 模块链路集成测试 — 参考软件测试分层 + 流水线集成."""

from __future__ import annotations

import time
from typing import Any, Callable, Awaitable

TestFn = Callable[[], Awaitable[dict[str, Any]]]


async def _run(name: str, layer: str, fn: TestFn) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        detail = await fn()
        ok = detail.pop("ok", True)
        return {
            "id": detail.get("id", name),
            "name": name,
            "layer": layer,
            "status": "pass" if ok else "fail",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000),
            **detail,
        }
    except Exception as e:
        return {
            "id": name,
            "name": name,
            "layer": layer,
            "status": "fail",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000),
            "error": str(e),
        }


async def run_integration_suite(selected: list[str] | None = None) -> dict[str, Any]:
    """运行 L5 集成测试集."""
    from security_agent.api import agent_plan

    results: list[dict[str, Any]] = []
    plan_cache: dict[str, Any] = {}

    async def t_l1_plan():
        plan = await agent_plan.build_analysis_plan("集成测试：查看系统健康")
        plan_cache["plan"] = plan
        return {"ok": bool(plan.get("plan_id")), "plan_id": plan.get("plan_id"), "trace_id": plan.get("trace_id")}

    async def t_l2_precheck():
        p = plan_cache.get("plan")
        if not p:
            return {"ok": False, "error": "缺少 L1 plan"}
        r = await agent_plan.run_l2_precheck(p["plan_id"])
        return {"ok": r.get("verdict") in ("pass", "confirm"), "verdict": r.get("verdict")}

    async def t_l3_execute():
        p = plan_cache.get("plan")
        if not p:
            return {"ok": False, "error": "缺少 plan"}
        r = await agent_plan.execute_plan(p["plan_id"], user_confirmed=True)
        plan_cache["execute"] = r
        return {"ok": bool(r.get("reply") or r.get("tools_used") is not None), "trace_id": r.get("trace_id")}

    async def t_l4_audit():
        ex = plan_cache.get("execute") or {}
        audit = ex.get("audit") or {}
        return {"ok": audit.get("audit_status") == "recorded", "audit": audit}

    async def t_l5_metrics():
        from security_agent.l5.analytics import build_scatter_from_traces

        scatter = build_scatter_from_traces([{"trace_id": "t", "duration_ms": 100, "intent": "health"}])
        return {"ok": "points" in scatter, "anomaly_count": scatter.get("anomaly_count")}

    async def t_link_l1_l2():
        p = plan_cache.get("plan")
        if not p:
            await t_l1_plan()
            p = plan_cache.get("plan")
        r = await agent_plan.run_l2_precheck(p["plan_id"])
        return {"ok": "verdict" in r, "link": "L1→L2"}

    async def t_link_l2_l3():
        p = plan_cache.get("plan")
        if not p:
            return {"ok": False, "error": "无 plan"}
        if p.get("l2_verdict") is None:
            await agent_plan.run_l2_precheck(p["plan_id"])
        try:
            await agent_plan.execute_plan(p["plan_id"], user_confirmed=True)
            return {"ok": True, "link": "L2→L3→L4"}
        except ValueError as e:
            return {"ok": False, "error": str(e), "link": "L2→L3"}

    suite: list[tuple[str, str, TestFn]] = [
        ("l1_plan", "L1", t_l1_plan),
        ("l2_precheck", "L2", t_l2_precheck),
        ("link_l1_l2", "L1-L2", t_link_l1_l2),
        ("l3_execute", "L3", t_l3_execute),
        ("l4_audit", "L4", t_l4_audit),
        ("link_l2_l3", "L2-L4", t_link_l2_l3),
        ("l5_metrics", "L5", t_l5_metrics),
    ]

    for tid, layer, fn in suite:
        if selected and tid not in selected:
            continue
        results.append(await _run(tid, layer, fn))

    passed = sum(1 for r in results if r["status"] == "pass")
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results) * 100, 1) if results else 0,
        "results": results,
    }

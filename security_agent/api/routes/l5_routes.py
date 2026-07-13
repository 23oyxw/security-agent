"""L5 分析 API — 散点/热力/溯源/集成测试."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User

router = APIRouter()


def _load_traces(limit: int = 200) -> list[dict]:
    from security_agent.storage.trace_catalog import load_shared_traces

    return load_shared_traces(limit=limit)


@router.get("/sync")
async def l5_sync_status(user: User = Depends(get_current_user)):
    """L5 与 L4 共用 Trace 目录状态."""
    traces = _load_traces(limit=200)
    return {
        "trace_count": len(traces),
        "latest_trace_id": traces[0].get("trace_id") if traces else None,
        "source": "trace_catalog",
        "l4_list": "/api/trace/",
    }


@router.get("/scatter")
async def l5_scatter(user: User = Depends(get_current_user)):
    from security_agent.l5.analytics import build_scatter_from_traces

    traces = _load_traces()
    return build_scatter_from_traces(traces)


@router.get("/heatmap")
async def l5_heatmap(user: User = Depends(get_current_user)):
    from security_agent.l5.analytics import build_heatmap_from_traces

    traces = _load_traces()
    return build_heatmap_from_traces(traces)


@router.get("/distributions")
async def l5_distributions(user: User = Depends(get_current_user)):
    from security_agent.l5.analytics import build_distributions_from_traces

    traces = _load_traces()
    return build_distributions_from_traces(traces)


@router.get("/layer-cross")
async def l5_layer_cross(user: User = Depends(get_current_user)):
    from security_agent.l5.analytics import build_layer_cross_report

    traces = _load_traces()
    l5_dims = None
    try:
        from security_agent.agent.evaluation import get_evaluator

        l5_dims = get_evaluator().l5_dimension_report()
    except Exception:
        pass
    return build_layer_cross_report(traces, l5_dims_report=l5_dims)


@router.get("/root-cause/{trace_id}")
async def l5_root_cause(trace_id: str, user: User = Depends(get_current_user)):
    from security_agent.l5.analytics import build_root_cause

    detail = None
    try:
        from security_agent.audit.spine import export_incident_bundle
        from security_agent.storage.trace_storage import get_trace_storage

        bundle = export_incident_bundle(trace_id)
        detail = bundle.get("sqlite_trace") or get_trace_storage().get_trace(trace_id)
        if detail and bundle.get("sqlite_trace"):
            detail = {**detail, "trace_id": trace_id}
    except Exception:
        try:
            from security_agent.storage.trace_storage import get_trace_storage

            detail = get_trace_storage().get_trace(trace_id)
        except Exception:
            detail = None
    if not detail:
        detail = {
            "trace_id": trace_id,
            "stages": [
                {"stage": "L1_analyze", "duration_ms": 120},
                {"stage": "L2_safety", "duration_ms": 45},
                {"stage": "L3_execute", "duration_ms": 890, "error": True},
                {"stage": "L4_audit", "duration_ms": 30},
            ],
        }
    return build_root_cause(detail)


class IntegrationRunRequest(BaseModel):
    test_ids: list[str] | None = None


@router.post("/integration/run")
async def l5_integration_run(req: IntegrationRunRequest, user: User = Depends(get_current_user)):
    from security_agent.l5.integration_tests import run_integration_suite

    return await run_integration_suite(req.test_ids)


class ExternalSimRequest(BaseModel):
    scenario_ids: list[str] | None = None


@router.get("/integration/external/catalog")
async def l5_external_catalog(user: User = Depends(get_current_user)):
    from security_agent.l5.external_sim import EXTERNAL_SCENARIOS

    return {
        "method": "external blackbox demo",
        "discovery_only": True,
        "scenarios": EXTERNAL_SCENARIOS,
    }


@router.post("/integration/external/run")
async def l5_external_run(req: ExternalSimRequest, user: User = Depends(get_current_user)):
    from security_agent.l5.external_sim import run_external_simulation

    return await run_external_simulation(req.scenario_ids)


@router.get("/policy-feedback")
async def l5_policy_feedback(user: User = Depends(get_current_user)):
    from security_agent.l5.policy_feedback import build_policy_hints, load_policy_hints

    try:
        from security_agent.agent.evaluation import get_evaluator

        dims = get_evaluator().dimension_scores()
        return build_policy_hints(dims)
    except Exception:
        return load_policy_hints()


@router.post("/policy-feedback/apply")
async def l5_policy_apply(user: User = Depends(get_current_user)):
    from security_agent.l5.policy_feedback import apply_policy_hints

    return apply_policy_hints()


@router.get("/clusters")
async def l5_clusters(user: User = Depends(get_current_user)):
    from security_agent.l5.cluster_analytics import cluster_boundary_hits, cluster_trace_latencies

    traces = _load_traces()
    boundary_hits: list[dict] = []
    try:
        from security_agent.storage.plan_store import get_plan_store

        for plan in (get_plan_store().list_recent(limit=20) or []):
            for hit in plan.get("boundary_hits") or []:
                if isinstance(hit, dict):
                    boundary_hits.append(hit)
    except Exception:
        pass

    return {
        "boundary": cluster_boundary_hits(boundary_hits),
        "traces": cluster_trace_latencies(traces) if traces else cluster_trace_latencies([
            {"trace_id": "demo-1", "duration_ms": 420, "error_rate": 0},
            {"trace_id": "demo-2", "duration_ms": 890, "error_rate": 12},
            {"trace_id": "demo-3", "duration_ms": 2100, "failed": True},
        ]),
    }


@router.get("/math-catalog")
async def l5_math_catalog(user: User = Depends(get_current_user)):
    return {
        "models": [
            {
                "id": "l1_dbscan_boundary",
                "layer": "L1",
                "name": "边界 DBSCAN-2D",
                "formula": "severity(verdict) x confidence(rule_count)",
                "oss": "pure Python DBSCAN (no sklearn)",
            },
            {
                "id": "l5_scatter_3sigma_iqr",
                "layer": "L5",
                "name": "散点 3sigma + IQR",
                "formula": "outlier if |x-mu|>3sigma or x outside [Q1-1.5IQR, Q3+1.5IQR]",
                "oss": "Python statistics",
            },
            {
                "id": "l5_heatmap_density",
                "layer": "L5",
                "name": "时段热力 weighted_density",
                "formula": "risk = duration/50 + failed*40",
                "oss": "ECharts heatmap",
            },
            {
                "id": "l5_trace_dbscan",
                "layer": "L5",
                "name": "链路 DBSCAN-2D",
                "formula": "cluster (latency_s, error_rate)",
                "oss": "cluster_analytics.py",
            },
            {
                "id": "l3_htn_0_1",
                "layer": "L3",
                "name": "HTN 0-1 工具路径",
                "formula": "min cost; order metrics->logs->repair->dispatch",
                "oss": "LangGraph-style; workflow_manifest.json",
            },
        ],
    }


@router.get("/integration/catalog")
async def l5_integration_catalog(user: User = Depends(get_current_user)):
    return {
        "method": "分层集成测试 · 模块链路选择",
        "reference": "pipeline E2E + 层间链接 + L5 指标（类 pytest integration / CI matrix）",
        "tests": [
            {"id": "l1_plan", "name": "L1 计划感知", "layer": "L1"},
            {"id": "l2_precheck", "name": "L2 安全预检", "layer": "L2"},
            {"id": "link_l1_l2", "name": "链路 L1→L2", "layer": "L1-L2"},
            {"id": "l3_execute", "name": "L3 执行分发", "layer": "L3"},
            {"id": "l4_audit", "name": "L4 审计卷宗", "layer": "L4"},
            {"id": "link_l2_l3", "name": "链路 L2→L3→L4", "layer": "L2-L4"},
            {"id": "l5_metrics", "name": "L5 指标模型", "layer": "L5"},
        ],
    }

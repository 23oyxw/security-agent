"""工作流路由 — 实时执行流程 + 快照状态聚合.

GET /api/workflow/standard              预置工作流定义
GET /api/workflow/flow-status           实时聚合状态（泳道面板数据源）
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import psutil
from fastapi import APIRouter, Depends

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User
from security_agent.monitor.dynamic_threshold import get_dynamic_threshold

router = APIRouter()

_MANIFEST_PATH = Path(__file__).resolve().parents[3] / "data" / "mcp" / "workflow_manifest.json"
_WORKFLOW_PATH = Path(__file__).resolve().parents[3] / "configs" / "workflows" / "autonomous_ops.json"
_WIKI_EXPORT_DIR = Path(__file__).resolve().parents[3] / "data" / "wiki_export"


def _load_manifest() -> dict[str, Any]:
    if _MANIFEST_PATH.is_file():
        return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"version": "1.0", "workflows": []}


@router.get("/manifest")
async def get_workflow_manifest(user: User = Depends(get_current_user)):
    """HTN 工作流标注清单 — 意图/簇/代价/层级/沙箱."""
    manifest = _load_manifest()
    from security_agent.pipeline.tool_taxonomy import TOOL_CLUSTERS, summarize_chain

    workflows = []
    for wf in manifest.get("workflows") or []:
        chain = wf.get("tool_chain") or []
        summary = summarize_chain(chain) if chain else {"clusters": {}, "total_cost": 0}
        workflows.append({
            **wf,
            "cluster_map": summary.get("clusters"),
            "total_cost": summary.get("total_cost"),
            "sandbox_required": summary.get("total_cost", 0) > 0,
        })
    return {
        "version": manifest.get("version"),
        "description": manifest.get("description"),
        "tier_labels": manifest.get("tier_labels", {}),
        "workflows": workflows,
    }


@router.get("/tier-catalog")
async def get_tier_catalog(user: User = Depends(get_current_user)):
    """分级目录 — 定义/流水线/数学/工作流/沙箱."""
    return {
        "tiers": [
            {"id": "T0", "name": "定义封装", "store": "data/mcp/workflow_manifest.json", "wiki": "wiki-export/T0-definition"},
            {"id": "T1", "name": "五层流水线", "store": "docs/architecture/FIVE_LAYER_PIPELINE.md", "wiki": "wiki-export/T1-pipeline"},
            {"id": "T2", "name": "数学量化", "store": "security_agent/l5/", "wiki": "wiki-export/T2-math"},
            {"id": "T3", "name": "工作流标注", "store": "data/mcp/workflow_manifest.json", "wiki": "wiki-export/T3-workflow"},
            {"id": "T4", "name": "沙箱全包", "store": "security_agent/pipeline/sandbox_gate.py", "wiki": "wiki-export/T4-sandbox"},
        ],
        "compare_doc": "docs/architecture/ARCHITECTURE_TIER_MAP.md",
    }


@router.get("/wiki-export/status")
async def wiki_export_status(user: User = Depends(get_current_user)):
    """Gitee Wiki 导出包状态."""
    files = []
    if _WIKI_EXPORT_DIR.is_dir():
        for p in sorted(_WIKI_EXPORT_DIR.glob("*.md")):
            files.append({"name": p.name, "size": p.stat().st_size})
    return {
        "export_dir": str(_WIKI_EXPORT_DIR),
        "files": files,
        "sync_script": "scripts/sync_gitee_wiki.sh",
        "build_script": "scripts/build_wiki_tier_bundle.py",
    }


@router.get("/spine")
async def get_main_spine(user: User = Depends(get_current_user)):
    """主线统筹 — 三 Agent + 五层 + MCP/Skill 分层 + 性能总览钩子."""
    from security_agent.agent.agent_registry import AGENT_REGISTRY, ORCHESTRATOR, TOOL_CLUSTERS
    from security_agent.contracts.loader import get_contract
    from security_agent.security.response_policy import apply_response_policy

    manifest = _load_manifest()
    perf: dict[str, Any] = {}
    try:
        import psutil
        perf["cpu_percent"] = psutil.cpu_percent(interval=0.05)
        perf["memory_percent"] = psutil.virtual_memory().percent
    except Exception:
        pass
    try:
        from security_agent.skills.registry import list_skills
        skill_count = len(list_skills())
    except Exception:
        skill_count = 0

    payload = {
        "formula": ORCHESTRATOR.get("formula"),
        "main_line": get_contract().get("main_line"),
        "auxiliary": get_contract().get("auxiliary"),
        "three_agents": AGENT_REGISTRY,
        "orchestrator": ORCHESTRATOR,
        "tool_clusters": TOOL_CLUSTERS,
        "tier_labels": manifest.get("tier_labels", {}),
        "workflow_count": len(manifest.get("workflows") or []),
        "encapsulation": {
            "manifest": "data/mcp/workflow_manifest.json",
            "mcp_api": "GET /api/mcp/servers",
            "skill_flow_api": "GET /api/skills/flows",
            "htn": "security_agent/pipeline/htn_planner.py",
        },
        "performance_snapshot": perf,
        "api_surface": {
            "orchestrate": "POST /api/agent/orchestrate",
            "task_analyze": "POST /api/reports/analyze",
            "inspection_run": "POST /api/inspection/run",
            "inspection_risk": "GET /api/inspection/risk/predict",
            "knowledge_rag": "POST /api/knowledge/rag",
            "repair": "POST /api/repair/trigger",
            "alerts": "GET /api/alerts/aggregated",
            "eval": "GET /api/eval/score",
            "l5": "GET /api/l5/scatter",
        },
    }
    return apply_response_policy(payload, user)


@router.post("/layer-check")
async def layer_check(body: dict[str, Any], user: User = Depends(get_current_user)):
    """层级检测 — stage/message → layer/tool/cluster 权威标注."""
    from security_agent.pipeline.stage_meta import enrich_stage_data
    from security_agent.security.response_policy import apply_response_policy

    stage = str(body.get("stage_name") or body.get("stage") or "L1_analyze")
    data = body.get("data") or {}
    message = body.get("message")
    if message and not data:
        from security_agent.analysis.task_analyzer import analyze_task
        analysis = analyze_task(str(message), user_role=user.role)
        return apply_response_policy({
            "mode": "message",
            "layers_detected": analysis.get("layers_detected"),
            "intent": analysis.get("intent"),
            "stage_preview": analysis.get("stage_preview"),
            "main_spine": analysis.get("main_spine"),
        }, user)
    enriched = enrich_stage_data(stage, dict(data))
    return apply_response_policy({"mode": "stage", "stage_name": stage, "enriched": enriched}, user)



@router.get("/standard")
async def get_standard_workflow(user: User = Depends(get_current_user)):
    """返回预置运维流程 JSON（只读，非编辑器）."""
    if _WORKFLOW_PATH.is_file():
        return json.loads(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    return {
        "title": "银河麒麟智能安全运维工作流",
        "description": "采集层 → 管控层 → 执行层 → 审计层",
        "steps": [
            {"id": "S1", "title": "OS 环境感知", "pillar": "① 感知", "api": "GET /api/perception/context", "detail": "自动采集 CPU/内存/磁盘/网络/进程快照"},
            {"id": "S2", "title": "MCP 插件注册", "pillar": "② MCP", "api": "GET /api/mcp/servers", "detail": "17+ Skill 自动发现，热插拔刷新"},
            {"id": "S3", "title": "安全意图校验", "pillar": "③ 安全", "api": "POST /api/safety/defense/evaluate", "detail": "L1 静态 30% + L2 意图 35% + L3 受限 35%"},
            {"id": "S4", "title": "受限沙箱执行", "pillar": "④ 执行", "api": "POST /api/executor/execute", "detail": "PrivilegeBroker 降权 + SandboxExecutor 隔离"},
            {"id": "S5", "title": "快照备份+回滚", "pillar": "④ 执行", "api": "POST /api/executor/rollback", "detail": "IRREVERSIBLE 操作前自动快照，失败自动恢复"},
            {"id": "S6", "title": "推理链路溯源", "pillar": "⑤ 审计", "api": "GET /api/trace/{id}/export", "detail": "事件脊柱 + 六阶段 tracing + 执行纪要导出"},
        ],
    }


@router.get("/flow-status")
async def flow_status(user: User = Depends(get_current_user)):
    """聚合实时状态 — 四个泳道完整快照.

    前端每 3 秒轮询此端点获取完整实时视图。
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    dt = get_dynamic_threshold().compute()

    # ============ 泳道 1: 采集层 ============
    cpu = psutil.cpu_percent(interval=0.05)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = psutil.getloadavg()

    collection = {
        "status": "active",
        "nodes": [
            {"id": "C1", "title": "CPU", "value": f"{cpu:.1f}%", "subtitle": f"负载 {load[0]:.1f}", "alert": cpu > dt.get("cpu_threshold", 80), "trend": "up" if cpu > 50 else "stable"},
            {"id": "C2", "title": "内存", "value": f"{mem.percent:.1f}%", "subtitle": f"已用 {mem.used // (1024**2)}MB", "alert": mem.percent > dt.get("memory_threshold", 90), "trend": "up" if mem.percent > 70 else "stable"},
            {"id": "C3", "title": "磁盘", "value": f"{disk.percent:.1f}%", "subtitle": f"剩余 {disk.free // (1024**3)}GB", "alert": disk.percent > dt.get("disk_threshold", 85), "trend": "up" if disk.percent > 75 else "stable"},
            {"id": "C4", "title": "活跃进程", "value": str(len(psutil.pids())), "subtitle": "psutil.pids()", "alert": False, "trend": "stable"},
            {"id": "C5", "title": "网络连接", "value": str(len(psutil.net_connections(kind="inet"))), "subtitle": "TCP/UDP", "alert": False, "trend": "stable"},
        ],
        "thresholds": dt,
    }

    # ============ 泳道 2: 管控层 (MCP + Skill) ============
    control: dict[str, Any] = {"status": "active", "nodes": []}
    try:
        from security_agent.skills.registry import list_skills
        skills = list_skills()
        control["nodes"] = [
            {"id": f"SK-{s['name']}", "title": s["display_name"], "value": f"{s['tool_count']} 工具", "subtitle": s.get("description", "")[:60], "alert": False}
            for s in skills[:8]
        ]
    except Exception:
        control["nodes"] = [{"id": "SK-err", "title": "MCP 注册中心", "value": "—", "subtitle": "加载中", "alert": False}]

    # ============ 泳道 3: 执行层 (快照) ============
    execution: dict[str, Any] = {"status": "active", "nodes": []}
    try:
        from security_agent.safety_gate.snapshot import SnapshotManager
        mgr = SnapshotManager()
        snaps = mgr.list_snapshots(limit=5)
        execution["nodes"] = [
            {
                "id": s.id,
                "title": s.operation[:60] or "快照",
                "value": s.risk_level,
                "subtitle": s.created_at[:19] if s.created_at else "",
                "alert": s.risk_level == "CRITICAL",
                "restored": bool(mgr._index.get(s.id, {}).get("restored_at")),
                "files_count": len(s.files_before),
            }
            for s in snaps
        ]
    except Exception:
        pass

    # ============ 泳道 4: 审计层 (Trace) ============
    audit_data: dict[str, Any] = {"status": "active", "nodes": []}
    try:
        from security_agent.audit.spine import incident_spine
        traces = incident_spine.recent_traces(5)
        audit_data["nodes"] = [
            {
                "id": t.get("trace_id", ""),
                "title": t.get("operation", "trace")[:60],
                "value": f"{t.get('stages', 0)} 阶段",
                "subtitle": t.get("started_at", "")[:19],
                "alert": not t.get("ok", True),
            }
            for t in traces
        ]
    except Exception:
        pass

    return {
        "timestamp": now,
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "layers": {
            "collection": collection,
            "control": control,
            "execution": execution,
            "audit": audit_data,
        },
    }

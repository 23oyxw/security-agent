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

_WORKFLOW_PATH = Path(__file__).resolve().parents[3] / "configs" / "workflows" / "autonomous_ops.json"


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

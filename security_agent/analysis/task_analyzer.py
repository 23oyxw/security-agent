"""Prompt / command task analysis."""

from __future__ import annotations
import json, re, uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from security_agent.pipeline.stage_meta import enrich_stage_data
from security_agent.security.redact import redact_text

_MANIFEST = Path(__file__).resolve().parents[2] / "data" / "mcp" / "workflow_manifest.json"
_INTENTS = [
    ("health", re.compile(r"健康|体检|health|cpu|内存|磁盘", re.I)),
    ("parallel_info", re.compile(r"并行|采集|扫描|scan", re.I)),
    ("full_check", re.compile(r"全量|全面|baseline", re.I)),
    ("repair", re.compile(r"修复|repair|回滚", re.I)),
    ("alert", re.compile(r"告警|alert", re.I)),
    ("research", re.compile(r"CVE|漏洞|威胁|研究|分析", re.I)),
]
_LAYERS = [
    ("L1", re.compile(r"计划|感知|知识|边界|analyze", re.I)),
    ("L2", re.compile(r"安全|沙箱|护栏|precheck", re.I)),
    ("GATE", re.compile(r"门禁|gate|审批", re.I)),
    ("L3", re.compile(r"执行|execute|mcp|skill", re.I)),
    ("L4", re.compile(r"trace|审计|卷宗", re.I)),
    ("L5", re.compile(r"量化|heatmap|l5", re.I)),
]
_REFS = [
    {"id": "htn", "title": "HTN Planning", "cite": "Erol et al. (1994)", "applies_to": "workflow_manifest"},
    {"id": "rag", "title": "RAG", "cite": "Lewis et al. (2020)", "applies_to": "L1 knowledge"},
    {"id": "sandbox", "title": "Capability Isolation", "cite": "Saltzer & Schroeder (1975)", "applies_to": "L2/L3"},
]

def _manifest():
    return json.loads(_MANIFEST.read_text(encoding="utf-8")) if _MANIFEST.is_file() else {"workflows": []}

def analyze_task(prompt: str, *, filename: Optional[str] = None, file_excerpt: Optional[str] = None, user_role: str = "operator") -> dict[str, Any]:
    raw = (prompt or "").strip()
    if file_excerpt:
        raw += f"\n\n--- file:{filename or 'upload'} ---\n{file_excerpt[:8000]}"
    safe = redact_text(raw)
    intent = next((n for n, p in _INTENTS if p.search(safe)), "general")
    layers = [l for l, p in _LAYERS if p.search(safe)] or ["L1", "L2", "GATE", "L3"]
    matches = []
    for wf in _manifest().get("workflows") or []:
        score = (3 if wf.get("intent") == intent else 0) + sum(1 for t in (wf.get("tool_chain") or []) if str(t).lower() in safe.lower())
        if score:
            matches.append({**wf, "match_score": score})
    matches.sort(key=lambda x: -x["match_score"])
    matches = matches[:5]
    high = bool(re.search(r"rm\s+-rf|chmod\s+777|passwd|sudo\s+su", safe, re.I))
    med = bool(re.search(r"kill|restart|rollback|repair|delete", safe, re.I))
    risk = {"level": "high" if high else ("medium" if med else "low"), "requires_l2": high or med, "sandbox_recommended": high}
    chain = list(matches[0].get("tool_chain") or []) if matches else []
    return {
        "analysis_id": uuid.uuid4().hex[:12],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "prompt_redacted": safe[:2000],
        "filename": filename,
        "intent": intent,
        "layers_detected": layers,
        "main_spine": [
            {"layer": "L1", "agent": "core_dispatch", "status": "required"},
            {"layer": "L2", "agent": "safety_sandbox", "status": "required"},
            {"layer": "GATE", "agent": "core_dispatch", "status": "required"},
            {"layer": "L3", "agent": "core_dispatch", "status": "conditional"},
            {"layer": "L4", "agent": "audit_iteration", "status": "auxiliary"},
            {"layer": "L5", "agent": "audit_iteration", "status": "auxiliary"},
        ],
        "three_agents": {
            "core_dispatch": "L1+L3 主线调度",
            "safety_sandbox": "L2 安全闸门",
            "audit_iteration": "L4+L5 辅助闭环",
        },
        "workflow_matches": matches,
        "suggested_tool_chain": chain,
        "skill_flow": matches[0].get("skill_flow") if matches else None,
        "risk": risk,
        "stage_preview": enrich_stage_data("L1_analyze_task", {"intent": intent, "tool_chain": chain}),
        "academic_refs": _REFS,
        "performance_hooks": {"eval": "/api/eval/score", "l5": "/api/l5/scatter", "metrics": "/api/perception/metrics"},
        "next_actions": [
            {"action": "orchestrate", "api": "POST /api/agent/orchestrate"},
            {"action": "knowledge", "api": "POST /api/knowledge/rag"},
            {"action": "repair", "api": "POST /api/repair/trigger"},
        ],
        "visibility": "full" if user_role == "admin" else "redacted",
    }

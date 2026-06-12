"""三智能体注册表 — 终版 v1.0，与 frontend/src/constants/agents.js 对齐."""

from __future__ import annotations

from typing import Any

AGENT_REGISTRY: list[dict[str, Any]] = [
    {
        "agent": "core_dispatch",
        "display_name": "核心调度代理",
        "layer": "L1+L3",
        "layer_note": "阶段锁 analyze→execute",
        "description": "L1 三感知：抗性边界·灵敏知识·静态之眼 | L3 推理·MCP",
        "phases": ["analyze", "execute"],
        "can_write": False,
        "can_write_in_phase": {"execute": True},
    },
    {
        "agent": "safety_sandbox",
        "display_name": "安全防护沙箱代理",
        "layer": "L2",
        "layer_note": "唯一安全闸门",
        "description": "意图(安全)·护栏·熔断·沙箱预演·二次确认",
        "phases": ["precheck"],
        "can_write": False,
    },
    {
        "agent": "audit_iteration",
        "display_name": "审计迭代代理",
        "layer": "L4+L5",
        "layer_note": "溯源·回流·量化",
        "description": "trace 卷宗·链路绘图·Wiki 回流·全维指标自进化",
        "phases": ["finalize"],
        "can_write": False,
    },
]

TOOL_CLUSTERS: list[dict[str, Any]] = [
    {"cluster": "metrics", "display_name": "指标采集", "examples": ["get_system_health", "query_security_scan_json"]},
    {"cluster": "logs", "display_name": "日志处理", "examples": ["get_audit_log", "journal 检索"]},
    {"cluster": "repair", "display_name": "故障修复", "examples": ["run_terminal_command", "block_process flow"]},
    {"cluster": "schedule", "display_name": "资源调度", "examples": ["run_autonomous_mission", "cpu_stress flow"]},
]

ORCHESTRATOR = {
    "id": "orchestrator",
    "display_name": "编排助手",
    "description": "前端双模式入口：计划模式(L1) / 执行模式(L3)，串联三代 Agent",
    "modes": ["plan", "execute"],
    "formula": "1调度 + 1安全 + 1迭代",
}

PIPELINE_LAYERS = ["L1", "L2", "L3", "L4", "L5"]


def default_agent_stages() -> list[dict[str, Any]]:
    return [
        {
            "agent": a["agent"],
            "display_name": a["display_name"],
            "layer": a["layer"],
            "status": "idle",
            "detail": "",
        }
        for a in AGENT_REGISTRY
    ]

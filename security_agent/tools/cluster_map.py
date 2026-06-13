"""四大工具簇 — 单工具单职责映射（开发/运维视图）."""

from __future__ import annotations

TOOL_CLUSTER: dict[str, str] = {
    "get_system_health": "metrics",
    "query_security_scan": "metrics",
    "query_security_scan_json": "metrics",
    "list_processes": "metrics",
    "check_exposed_ports": "metrics",
    "list_network_connections": "metrics",
    "get_monitor_events": "metrics",
    "get_audit_log": "logs",
    "search_security_knowledge": "logs",
    "run_terminal_command": "repair",
    "block_high_risk_process": "repair",
    "generate_security_report": "logs",
    "run_full_security_check": "metrics",
    "run_autonomous_mission": "dispatch",
    "start_monitor": "dispatch",
    "stop_monitor": "dispatch",
}

CLUSTER_LABELS = {
    "metrics": "指标采集",
    "logs": "日志处理",
    "repair": "故障修复",
    "dispatch": "资源调度",
}


def cluster_for_tool(name: str) -> str:
    return TOOL_CLUSTER.get(name, "general")

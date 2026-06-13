"""L3 tool clusters and 0-1 cost model."""

from __future__ import annotations

from typing import Any

TOOL_CLUSTERS: dict[str, list[str]] = {
    "metrics": [
        "get_system_health",
        "query_security_scan_json",
        "query_security_scan",
        "list_processes",
        "check_exposed_ports",
        "get_monitor_events",
    ],
    "logs": [
        "get_audit_log",
        "generate_security_report",
    ],
    "repair": [
        "run_full_security_check",
        "run_terminal_command",
    ],
    "dispatch": [
        "run_autonomous_mission",
        "start_monitor",
        "stop_monitor",
    ],
}

_TOOL_COST: dict[str, int] = {
    "get_system_health": 0,
    "query_security_scan_json": 0,
    "query_security_scan": 0,
    "list_processes": 0,
    "check_exposed_ports": 0,
    "get_monitor_events": 0,
    "get_audit_log": 0,
    "generate_security_report": 0,
    "run_full_security_check": 1,
    "run_terminal_command": 1,
    "run_autonomous_mission": 1,
    "start_monitor": 1,
    "stop_monitor": 1,
}

_CLUSTER_ORDER = ("metrics", "logs", "repair", "dispatch")


def classify_tool(tool_name: str) -> str:
    for cluster, names in TOOL_CLUSTERS.items():
        if tool_name in names:
            return cluster
    return "dispatch"


def tool_cost(tool_name: str) -> int:
    return _TOOL_COST.get(tool_name, 1)


def cluster_order_key(tool_name: str) -> int:
    cluster = classify_tool(tool_name)
    try:
        return _CLUSTER_ORDER.index(cluster)
    except ValueError:
        return len(_CLUSTER_ORDER)


def summarize_chain(chain: list[str]) -> dict[str, Any]:
    by_cluster: dict[str, list[str]] = {k: [] for k in _CLUSTER_ORDER}
    for name in chain:
        by_cluster[classify_tool(name)].append(name)
    return {
        "clusters": {k: v for k, v in by_cluster.items() if v},
        "total_cost": sum(tool_cost(t) for t in chain),
        "read_only_cost": sum(tool_cost(t) for t in chain if tool_cost(t) == 0),
    }

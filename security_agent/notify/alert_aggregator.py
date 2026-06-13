"""Alert storm prevention: aggregate, dedupe, root-cause suppress."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

_DERIVATIVE_OF: dict[str, str] = {
    "服务宕机": "磁盘爆满",
    "进程异常退出": "磁盘爆满",
    "连接超时": "磁盘爆满",
    "内存告警": "磁盘爆满",
    "衍生告警": "磁盘爆满",
}

_DEFAULT_WINDOW_MIN = 5

_ALERT_TAXONOMY: dict[str, dict[str, str]] = {
    "磁盘爆满": {"category": "infra", "grade": "P0", "action": "repair_disk_cleanup"},
    "CPU告警": {"category": "performance", "grade": "P1", "action": "scale_or_throttle"},
    "内存告警": {"category": "performance", "grade": "P1", "action": "inspect_process"},
    "服务宕机": {"category": "availability", "grade": "P0", "action": "restart_service"},
    "连接超时": {"category": "network", "grade": "P2", "action": "check_network"},
    "进程异常退出": {"category": "runtime", "grade": "P1", "action": "inspect_logs"},
    "安全事件": {"category": "security", "grade": "P0", "action": "isolate_and_audit"},
    "权限越界": {"category": "security", "grade": "P0", "action": "l2_block"},
}


def _classify_alert(alert: dict[str, Any]) -> dict[str, str]:
    etype = str(alert.get("type") or alert.get("title") or "event")
    sev = str(alert.get("level") or alert.get("severity") or "low").lower()
    tax = _ALERT_TAXONOMY.get(etype, {})
    grade = tax.get("grade") or (
        "P0" if sev in ("critical", "严重") else
        "P1" if sev in ("high", "高") else
        "P2" if sev in ("medium", "中") else "P3"
    )
    return {
        "category": tax.get("category") or "general",
        "grade": grade,
        "recommended_action": tax.get("action") or "review_trace",
        "taxonomy_source": "manifest" if etype in _ALERT_TAXONOMY else "severity_fallback",
    }


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def _group_key(alert: dict[str, Any]) -> str:
    etype = str(alert.get("type") or alert.get("title") or "event")
    source = str(alert.get("source") or alert.get("type") or "monitor")
    return f"{source}:{etype}"


def aggregate_alerts(
    alerts: list[dict[str, Any]],
    *,
    window_minutes: int = _DEFAULT_WINDOW_MIN,
) -> dict[str, Any]:
    if not alerts:
        return {
            "groups": [],
            "display_alerts": [],
            "suppressed_count": 0,
            "raw_count": 0,
            "window_minutes": window_minutes,
        }

    now = datetime.now()
    window = timedelta(minutes=window_minutes)
    sorted_alerts = sorted(
        alerts,
        key=lambda a: _parse_ts(a.get("ts") or a.get("timestamp") or a.get("published_at")) or now,
        reverse=True,
    )

    groups: dict[str, dict[str, Any]] = {}
    suppressed = 0
    root_types_seen: set[str] = set()
    severity_rank = {"critical": 4, "严重": 4, "high": 3, "高": 3, "medium": 2, "中": 2, "low": 1, "低": 1, "info": 0}

    for alert in sorted_alerts:
        ts = _parse_ts(alert.get("ts") or alert.get("timestamp") or alert.get("published_at"))
        if ts and (now - ts) > window:
            continue

        etype = str(alert.get("type") or alert.get("title") or "event")
        root = _DERIVATIVE_OF.get(etype)
        if root and root in root_types_seen:
            suppressed += 1
            continue

        key = _group_key(alert)
        sev = str(alert.get("level") or alert.get("severity") or "low").lower()
        rank = severity_rank.get(sev, 1)

        if key not in groups:
            taxonomy = _classify_alert(alert)
            groups[key] = {
                "group_id": hashlib.md5(key.encode()).hexdigest()[:10],
                "key": key,
                "type": etype,
                "source": alert.get("source") or alert.get("type") or "monitor",
                "count": 1,
                "severity": sev,
                "severity_rank": rank,
                "first_at": alert.get("ts") or alert.get("timestamp"),
                "last_at": alert.get("ts") or alert.get("timestamp"),
                "sample_message": (alert.get("message") or "")[:200],
                "alert_ids": [str(alert.get("id") or "")],
                "is_root": root is None,
                **taxonomy,
            }
            if root is None:
                root_types_seen.add(etype)
        else:
            g = groups[key]
            g["count"] += 1
            g["last_at"] = alert.get("ts") or alert.get("timestamp") or g["last_at"]
            if rank > g["severity_rank"]:
                g["severity"] = sev
                g["severity_rank"] = rank
            aid = str(alert.get("id") or "")
            if aid:
                g["alert_ids"].append(aid)

    group_list = sorted(groups.values(), key=lambda g: (-g["severity_rank"], -g["count"]))
    display = []
    for g in group_list:
        display.append({
            "id": g["group_id"],
            "title": g["type"],
            "source": g["source"],
            "severity": g["severity"],
            "category": g.get("category"),
            "grade": g.get("grade"),
            "recommended_action": g.get("recommended_action"),
            "message": g["sample_message"] if g["count"] == 1 else f"{g['sample_message']}（合并 {g['count']} 条）",
            "count": g["count"],
            "aggregated": g["count"] > 1,
            "first_at": g["first_at"],
            "last_at": g["last_at"],
            "alert_ids": g["alert_ids"],
            "storm_suppressed": False,
        })

    return {
        "groups": group_list,
        "display_alerts": display,
        "suppressed_count": suppressed,
        "raw_count": len(alerts),
        "display_count": len(display),
        "window_minutes": window_minutes,
        "method": "window_aggregate + derivative_suppress",
    }


def _event_type(alert: dict[str, Any]) -> str:
    return str(alert.get("type") or alert.get("title") or "event")


def _in_window(alert: dict[str, Any], *, now: datetime, window: timedelta) -> bool:
    ts = _parse_ts(alert.get("ts") or alert.get("timestamp") or alert.get("published_at"))
    if not ts:
        return True
    return (now - ts) <= window


def _root_types_in_window(alerts: list[dict[str, Any]], *, now: datetime, window: timedelta) -> set[str]:
    roots: set[str] = set()
    for alert in alerts:
        if not _in_window(alert, now=now, window=window):
            continue
        etype = _event_type(alert)
        if etype not in _DERIVATIVE_OF:
            roots.add(etype)
    return roots


def evaluate_publish(
    event: dict[str, Any],
    recent: list[dict[str, Any]],
    *,
    window_minutes: int = _DEFAULT_WINDOW_MIN,
) -> dict[str, Any]:
    now = datetime.now()
    window = timedelta(minutes=window_minutes)
    etype = _event_type(event)
    root = _DERIVATIVE_OF.get(etype)
    if root:
        roots_seen = _root_types_in_window(recent, now=now, window=window)
        if root in roots_seen:
            return {"publish": False, "notify": False, "increment_unread": False, "reason": "derivative_suppress", "root_type": root}
    key = _group_key(event)
    dup_count = sum(1 for a in recent if _in_window(a, now=now, window=window) and _group_key(a) == key)
    if dup_count > 0:
        return {"publish": True, "notify": False, "increment_unread": False, "storm_suppressed": True, "reason": "window_dedupe", "merge_count": dup_count + 1, "group_key": key}
    return {"publish": True, "notify": True, "increment_unread": True, "storm_suppressed": False, "reason": "normal", "group_key": key}
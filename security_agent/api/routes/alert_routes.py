"""告警路由"""

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from security_agent.api.deps import get_current_user
from security_agent.auth.models import User
from security_agent import config

router = APIRouter()

_LEVEL_MAP = {
    "严重": "critical",
    "高": "high",
    "中": "medium",
    "低": "low",
    "信息": "low",
}


class BatchAckRequest(BaseModel):
    alert_ids: list[str] | None = None  # None = acknowledge all


class BatchDeleteRequest(BaseModel):
    alert_ids: list[str] | None = None  # None = delete all


def _normalize_alert(raw: dict, idx: int) -> dict:
    from security_agent.timeutil import format_display

    level = str(raw.get("level", raw.get("severity", "low")))
    occurred_raw = raw.get("ts") or raw.get("timestamp") or ""
    published_raw = raw.get("published_at") or ""
    display_raw = occurred_raw or published_raw
    return {
        "id": raw.get("id") or f"alert-{idx}",
        "occurred_at": format_display(occurred_raw) if occurred_raw else "—",
        "occurred_at_raw": occurred_raw,
        "published_at": format_display(published_raw) if published_raw else "—",
        "published_at_raw": published_raw,
        "timestamp": format_display(display_raw) if display_raw else "—",
        "timestamp_raw": display_raw,
        "source": raw.get("type") or raw.get("source", "monitor"),
        "severity": _LEVEL_MAP.get(level, level.lower() if level else "low"),
        "level": _LEVEL_MAP.get(level, level.lower() if level else "low"),
        "title": raw.get("type") or raw.get("title", "告警"),
        "message": raw.get("message", ""),
        "acknowledged": bool(raw.get("read") or raw.get("acknowledged")),
    }


@router.get("/")
async def list_alerts(limit: int = 50, severity: str = "", user: User = Depends(get_current_user)):
    """列出告警"""
    try:
        from security_agent.notify.alerts import get_suppress_stats, read_recent_alerts

        items = [_normalize_alert(a, i) for i, a in enumerate(read_recent_alerts(limit=limit))]
        if severity:
            items = [a for a in items if a["severity"] == severity]
        return {"alerts": items, "total": len(items)}
    except Exception:
        return {"alerts": [], "total": 0}


@router.get("/active")
async def active_alerts(user: User = Depends(get_current_user)):
    """未确认告警"""
    data = await list_alerts(limit=100, severity="", user=user)
    active = [a for a in data["alerts"] if not a["acknowledged"]]
    return {"alerts": active, "count": len(active)}


@router.get("/unread-count")
async def unread_count(user: User = Depends(get_current_user)):
    """未读告警数（顶栏角标）"""
    try:
        from security_agent.notify.alerts import get_unread_count

        return {"count": get_unread_count()}
    except Exception:
        return {"count": 0}


@router.post("/{alert_id}/acknowledge")
async def ack_alert(alert_id: str, user: User = Depends(get_current_user)):
    """确认单条告警"""
    return await _ack_alerts(user, alert_ids=[alert_id])


@router.post("/acknowledge-batch")
async def ack_alerts_batch(body: BatchAckRequest, user: User = Depends(get_current_user)):
    """批量确认告警。不传 alert_ids 则确认全部"""
    return await _ack_alerts(user, alert_ids=body.alert_ids)


async def _ack_alerts(user: User, alert_ids: list[str] | None = None):
    path = config.DATA_DIR / "alerts" / "events.jsonl"
    if not path.exists():
        return {"ok": True, "acknowledged_count": 0}

    target_ids = set(alert_ids) if alert_ids else None
    lines = path.read_text(encoding="utf-8").splitlines()
    acked = 0
    updated: list[str] = []

    import json

    for line in lines:
        line = line.strip()
        if not line:
            updated.append(line)
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            updated.append(line)
            continue
        rid = str(rec.get("id") or "")
        if target_ids is None or rid in target_ids:
            rec["acknowledged"] = True
            rec["read"] = True
            rec["acknowledged_by"] = user.username
            acked += 1
        updated.append(json.dumps(rec, ensure_ascii=False))

    path.write_text("\n".join(updated) + "\n", encoding="utf-8")

    # 重置未读数
    try:
        from security_agent.notify.alerts import get_unread_count

        count_path = config.DATA_DIR / "alerts" / "unread.count"
        count_path.write_text("0", encoding="utf-8")
    except Exception:
        pass

    return {"ok": True, "acknowledged_count": acked, "acknowledged_by": user.username}


@router.delete("/")
async def delete_alerts(body: BatchDeleteRequest, user: User = Depends(get_current_user)):
    """批量删除告警。不传 alert_ids 则清空全部"""
    path = config.DATA_DIR / "alerts" / "events.jsonl"
    if not path.exists():
        return {"ok": True, "deleted_count": 0}

    target_ids = set(body.alert_ids) if body.alert_ids else None
    if target_ids is None:
        path.write_text("", encoding="utf-8")
        return {"ok": True, "deleted_count": -1, "message": "已清空全部告警"}

    lines = path.read_text(encoding="utf-8").splitlines()
    deleted = 0
    updated: list[str] = []

    import json

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            updated.append(line)
            continue
        rid = str(rec.get("id") or "")
        if rid in target_ids:
            deleted += 1
        else:
            updated.append(line)

    path.write_text("\n".join(updated) + ("\n" if updated else ""), encoding="utf-8")
    return {"ok": True, "deleted_count": deleted, "acknowledged_by": user.username}


@router.get("/aggregated")
async def aggregated_alerts(window_minutes: int = 5, user: User = Depends(get_current_user)):
    """防告警风暴：窗口聚合 + 衍生告警抑制."""
    try:
        from security_agent.notify.alerts import get_suppress_stats, read_recent_alerts
        from security_agent.notify.alert_aggregator import aggregate_alerts

        raw = read_recent_alerts(limit=200)
        agg = aggregate_alerts(raw, window_minutes=window_minutes)
        agg["publish_suppress"] = get_suppress_stats()
        from security_agent.security.response_policy import apply_response_policy
        return apply_response_policy(agg, user)
    except Exception as e:
        return {"groups": [], "display_alerts": [], "error": str(e), "raw_count": 0}


@router.get("/stats")
async def alert_stats(user: User = Depends(get_current_user)):
    """告警统计：按级别和状态汇总"""
    path = config.DATA_DIR / "alerts" / "events.jsonl"
    if not path.exists():
        return {"total": 0, "by_level": {}, "acknowledged": 0, "unacknowledged": 0}

    import json

    by_level: dict[str, int] = {}
    acked = 0
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        lv = str(rec.get("level", rec.get("severity", "low"))).lower()
        by_level[lv] = by_level.get(lv, 0) + 1
        if rec.get("acknowledged") or rec.get("read"):
            acked += 1

    return {
        "total": total,
        "by_level": by_level,
        "acknowledged": acked,
        "unacknowledged": total - acked,
    }
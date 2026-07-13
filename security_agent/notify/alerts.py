"""后台监控告警 — 写入文件 + 可选桌面通知（notify-send）."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.timeutil import format_display, now_iso

_NOTIFY_LEVELS = frozenset({"严重", "高"})
_SKIP_TYPES = frozenset({"心跳", "监控启动", "监控停止", "新进程"})


def _alerts_dir() -> Path:
    d = config.DATA_DIR / "alerts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _notify_enabled() -> bool:
    return os.getenv("NOTIFY_DESKTOP", "true").lower() in ("1", "true", "yes")


def _should_publish(event: dict[str, Any]) -> bool:
    level = str(event.get("level", ""))
    etype = str(event.get("type", ""))
    if level in _NOTIFY_LEVELS:
        return True
    if etype in ("监控错误", "敏感文件变更", "登录失败暴破", "新增监听端口"):
        return level != "信息"
    return False


def format_alert_line(event: dict[str, Any]) -> str:
    ts = format_display(event.get("ts"), "%Y-%m-%d %H:%M:%S")
    level = event.get("level", "?")
    etype = event.get("type", "事件")
    msg = event.get("message", "")[:200]
    return f"[{ts}] [{level}] {etype}: {msg}"


def _desktop_notify(title: str, body: str, urgency: str = "normal") -> None:
    if not _notify_enabled():
        return
    if not shutil.which("notify-send"):
        return
    try:
        subprocess.run(
            [
                "notify-send",
                "-a",
                "security-agent",
                "-u",
                urgency,
                title,
                body[:240],
            ],
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _record_publish_suppression(event: dict[str, Any], decision: dict[str, Any]) -> None:
    """Audit trail for publish-path storm suppression."""
    adir = _alerts_dir()
    payload = {
        "ts": now_iso(),
        "event_type": event.get("type"),
        "level": event.get("level"),
        "reason": decision.get("reason"),
        "message": (event.get("message") or "")[:200],
    }
    line = json.dumps(payload, ensure_ascii=False)
    with (adir / "suppressed.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    stats_path = adir / "suppress_stats.json"
    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stats = {"total_suppressed": 0, "derivative_suppress": 0, "window_dedupe": 0}
    stats["total_suppressed"] = int(stats.get("total_suppressed", 0)) + 1
    reason = str(decision.get("reason") or "unknown")
    stats[reason] = int(stats.get(reason, 0)) + 1
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def get_suppress_stats() -> dict[str, Any]:
    path = _alerts_dir() / "suppress_stats.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"total_suppressed": 0, "derivative_suppress": 0, "window_dedupe": 0}


def publish_monitor_event(event: dict[str, Any]) -> None:
    """监控线程调用：高/严重事件落盘并尝试桌面弹窗.

    降噪链路（v0.9 增强）:
        1. _should_publish()          — 基本过滤
        2. evaluate_publish()          — 去重 + 衍生抑制（已有）
        3. FrequencyThrottle           — 频率节流（新增）
        4. FloatingController          — 智能浮屏（新增）
    """
    if not _should_publish(event):
        return

    from security_agent.notify.alert_aggregator import evaluate_publish
    from security_agent.notify.throttle import get_throttle
    from security_agent.notify.floating import get_floating

    recent = read_recent_alerts(limit=200)
    decision = evaluate_publish(event, recent)
    if not decision.get("publish", True):
        _record_publish_suppression(event, decision)
        return

    # ---- v0.9: 频率节流 ----
    level = str(event.get("level", "低"))
    etype = str(event.get("type", "事件"))
    source = str(event.get("source", event.get("type", "monitor")))
    throttle_key = f"{source}:{etype}"

    # grade 映射
    grade_map = {"严重": "P0", "critical": "P0", "高": "P1", "high": "P1",
                  "中": "P2", "medium": "P2", "低": "P3", "low": "P3"}
    grade = grade_map.get(level, "P2")

    throttle = get_throttle()
    should_emit, throttle_reason, pending_count = throttle.should_emit(throttle_key, grade=grade)

    adir = _alerts_dir()
    record = {
        **event,
        "published_at": now_iso(),
        "read": False,
    }
    if decision.get("storm_suppressed"):
        record["storm_suppressed"] = True
        record["merge_count"] = decision.get("merge_count", 1)
        record["suppress_reason"] = decision.get("reason", "window_dedupe")

    # 被节流的事件仍写日志，但不推送
    if not should_emit:
        record["throttled"] = True
        record["throttle_reason"] = throttle_reason
        record["pending_count"] = pending_count
        line = json.dumps(record, ensure_ascii=False)
        with (adir / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        with (adir / "alerts.log").open("a", encoding="utf-8") as f:
            f.write(format_alert_line(event) + f" [节流: {throttle_reason}]\n")
        return

    # 合并积压信息
    if pending_count > 0:
        record["merged_pending"] = pending_count
        record["throttle_note"] = throttle_reason

    line = json.dumps(record, ensure_ascii=False)

    with (adir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    with (adir / "alerts.log").open("a", encoding="utf-8") as f:
        suffix = ""
        if decision.get("storm_suppressed"):
            suffix = f" [降噪合并×{record.get('merge_count', 1)}]"
        if pending_count > 0:
            suffix += f" [积压{pending_count}条]"
        f.write(format_alert_line(event) + suffix + "\n")

    # ---- v0.9: 智能浮屏 ----
    floating = get_floating()
    unread = get_unread_count()
    action = floating.decide(event, unread_count=unread)

    if action.level != "silent":
        (adir / "latest.json").write_text(line, encoding="utf-8")

    if action.level in ("badge", "toast", "banner", "modal"):
        unread_path = adir / "unread.count"
        try:
            n = int(unread_path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            n = 0
        unread_path.write_text(str(n + 1), encoding="utf-8")

    # 桌面通知仅在需要时发送
    if action.level in ("banner", "modal"):
        _desktop_notify(
            action.title,
            action.body,
            urgency=action.urgency,
        )

    # 存储浮屏决策供前端使用
    record["floating"] = action.to_dict()


def snooze_alert(source: str, alert_type: str, duration_minutes: int = 60) -> dict[str, Any]:
    """用户主动暂时忽略某类告警.

    Args:
        source: 告警来源（如 "monitor"）
        alert_type: 告警类型（如 "CPU告警"）
        duration_minutes: 忽略时长（分钟，默认 60）

    Returns:
        {"snoozed": True, "key": "...", "until": "..."}
    """
    from security_agent.notify.throttle import get_throttle

    key = f"{source}:{alert_type}"
    throttle = get_throttle()
    throttle.snooze(key, duration_sec=duration_minutes * 60)

    import datetime
    until = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)

    return {
        "snoozed": True,
        "key": key,
        "duration_minutes": duration_minutes,
        "until": until.isoformat(),
    }


def unsnooze_alert(source: str, alert_type: str) -> dict[str, Any]:
    """取消暂时忽略."""
    from security_agent.notify.throttle import get_throttle

    key = f"{source}:{alert_type}"
    throttle = get_throttle()
    ok = throttle.unsnooze(key)
    return {"unsnoozed": ok, "key": key}


def get_alert_pipeline_status() -> dict[str, Any]:
    """获取告警 pipeline 完整状态（供 UI/健康检查）."""
    from security_agent.notify.throttle import get_throttle
    from security_agent.notify.floating import get_floating
    return {
        "throttle": get_throttle().status(),
        "floating": get_floating().status(),
        "suppression": get_suppress_stats(),
        "unread": get_unread_count(),
    }


def read_recent_alerts(limit: int = 50) -> list[dict[str, Any]]:
    path = _alerts_dir() / "events.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))


def get_unread_count() -> int:
    path = _alerts_dir() / "unread.count"
    try:
        return max(0, int(path.read_text(encoding="utf-8").strip() or "0"))
    except (OSError, ValueError):
        return 0


def mark_alerts_read() -> None:
    path = _alerts_dir() / "unread.count"
    path.write_text("0", encoding="utf-8")

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


def publish_monitor_event(event: dict[str, Any]) -> None:
    """监控线程调用：高/严重事件落盘并尝试桌面弹窗."""
    if not _should_publish(event):
        return

    adir = _alerts_dir()
    record = {
        **event,
        "published_at": now_iso(),
        "read": False,
    }
    line = json.dumps(record, ensure_ascii=False)

    with (adir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    with (adir / "alerts.log").open("a", encoding="utf-8") as f:
        f.write(format_alert_line(event) + "\n")

    (adir / "latest.json").write_text(line, encoding="utf-8")

    unread_path = adir / "unread.count"
    try:
        n = int(unread_path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        n = 0
    unread_path.write_text(str(n + 1), encoding="utf-8")

    level = str(event.get("level", ""))
    urgency = "critical" if level == "严重" else "normal"
    _desktop_notify(
        f"安全运维告警 [{level}]",
        format_alert_line(event),
        urgency=urgency,
    )


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

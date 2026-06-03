"""时间工具 — 统一使用北京时间 (Asia/Shanghai, UTC+8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo

    TZ_BEIJING = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ_BEIJING = timezone(timedelta(hours=8))

TZ_LABEL = "北京时间"


def now_beijing() -> datetime:
    return datetime.now(TZ_BEIJING)


def now_iso() -> str:
    """带 +08:00 偏移的 ISO 时间，供日志/扫描/监控写入."""
    return now_beijing().isoformat(timespec="seconds")


def now_filename_ts() -> str:
    return now_beijing().strftime("%Y%m%d_%H%M%S")


def parse_iso(value: str | datetime | None, *, assume_utc_if_naive: bool = False) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        # Python 3.10 兼容: +08:00 → +0800
        if len(s) >= 6 and s[-6] in "+-" and s[-3] == ":":
            s = s[:-3] + s[-2:]
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    dt = datetime.strptime(s[:26], fmt)
                    break
                except ValueError:
                    dt = None
            if dt is None:
                return None
    if dt.tzinfo is None:
        if assume_utc_if_naive:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.replace(tzinfo=TZ_BEIJING)
    return dt.astimezone(TZ_BEIJING)


def format_storage_timestamp(value: str | datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """SQLite CURRENT_TIMESTAMP 等为 UTC 无时区字符串时使用."""
    if value is None or value == "":
        return "—"
    s = str(value).strip()
    assume_utc = bool(
        s
        and "T" not in s
        and "+" not in s
        and "Z" not in s
        and len(s) >= 19
        and s[4] == "-"
    )
    dt = parse_iso(value, assume_utc_if_naive=assume_utc)
    if dt is None:
        return s[:19] if len(s) >= 19 else s
    return dt.strftime(fmt)


def format_display(
    value: str | datetime | None,
    fmt: str = "%Y-%m-%d %H:%M:%S",
    *,
    with_label: bool = False,
    assume_utc_if_naive: bool = False,
) -> str:
    s = str(value or "").strip()
    if not s:
        return "—"
    if "T" not in s and "+" not in s and "Z" not in s and len(s) >= 19 and s[4] == "-":
        assume_utc_if_naive = True
    dt = parse_iso(value, assume_utc_if_naive=assume_utc_if_naive)
    if dt is None:
        return format_storage_timestamp(value, fmt)
    text = dt.strftime(fmt)
    return f"{text} ({TZ_LABEL})" if with_label else text


def format_file_mtime(path: str | Path, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    p = Path(path)
    ts = datetime.fromtimestamp(p.stat().st_mtime, tz=TZ_BEIJING)
    return ts.strftime(fmt)

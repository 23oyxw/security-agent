"""auth.log 登录失败/异常登录监测."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.security.redact import redact_text

_FAILED = re.compile(
    r"(?i)Failed\s+password\s+for\s+(?:invalid user\s+)?(\S+).*from\s+(\S+)",
)
_INVALID = re.compile(r"(?i)Invalid\s+user\s+(\S+)\s+from\s+(\S+)")
_ACCEPTED_PWD = re.compile(
    r"(?i)Accepted\s+password\s+for\s+(\S+)\s+from\s+(\S+)",
)


class AuthLogWatcher:
    def __init__(self) -> None:
        self._offsets: dict[str, int] = {}
        self._fail_window: list[float] = []

    def _resolve_path(self) -> Path | None:
        for p in config.AUTH_LOG_PATHS:
            path = Path(p)
            if path.exists() and path.is_file():
                return path
        return None

    def poll(self) -> list[dict[str, Any]]:
        path = self._resolve_path()
        if not path:
            return []

        key = str(path)
        try:
            size = path.stat().st_size
            offset = self._offsets.get(key, 0)
            if size < offset:
                offset = 0
            if size == offset:
                return []
            with path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                chunk = f.read(65536)
                self._offsets[key] = f.tell()
        except OSError:
            return []

        events: list[dict[str, Any]] = []
        fail_count = 0
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            safe_line = redact_text(line)

            m = _FAILED.search(line)
            if m:
                fail_count += 1
                events.append(
                    {
                        "type": "登录失败",
                        "level": "高",
                        "user": m.group(1),
                        "source_ip": m.group(2),
                        "message": safe_line[:240],
                        "raw_redacted": True,
                    }
                )
                continue

            m = _INVALID.search(line)
            if m:
                fail_count += 1
                events.append(
                    {
                        "type": "无效用户登录尝试",
                        "level": "高",
                        "user": m.group(1),
                        "source_ip": m.group(2),
                        "message": safe_line[:240],
                    }
                )
                continue

            m = _ACCEPTED_PWD.search(line)
            if m:
                events.append(
                    {
                        "type": "密码登录成功",
                        "level": "中",
                        "user": redact_text(m.group(1)),
                        "source_ip": m.group(2),
                        "message": safe_line[:240],
                    }
                )

        if fail_count >= config.AUTH_FAIL_BURST_THRESHOLD:
            events.append(
                {
                    "type": "暴破疑似",
                    "level": "严重",
                    "message": f"本轮巡检新增 {fail_count} 次失败登录（阈值 {config.AUTH_FAIL_BURST_THRESHOLD}）",
                    "fail_count": fail_count,
                }
            )
        return events

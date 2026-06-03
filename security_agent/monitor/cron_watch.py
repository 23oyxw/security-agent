"""Cron / 计划任务变更监测."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

def _file_sig(path: Path) -> str | None:
    try:
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()[:16]
    except OSError:
        return None


def collect_cron_signatures() -> dict[str, str]:
    sigs: dict[str, str] = {}
    paths: list[Path] = [Path("/etc/crontab")]
    cron_d = Path("/etc/cron.d")
    if cron_d.is_dir():
        paths.extend(p for p in sorted(cron_d.iterdir()) if p.is_file())
    for spool in (Path("/var/spool/cron/crontabs"), Path("/var/spool/cron")):
        if not spool.is_dir():
            continue
        try:
            paths.extend(p for p in sorted(spool.iterdir()) if p.is_file())
        except OSError:
            continue
    for p in paths:
        if p.is_file():
            s = _file_sig(p)
            if s:
                sigs[str(p)] = s
    return sigs


def diff_cron(
    previous: dict[str, str],
    current: dict[str, str],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path, sig in current.items():
        prev = previous.get(path)
        if prev is None:
            events.append(
                {
                    "type": "计划任务新增",
                    "level": "高",
                    "path": path,
                    "message": f"新增 cron 文件: {path}",
                }
            )
        elif prev != sig:
            events.append(
                {
                    "type": "计划任务变更",
                    "level": "高",
                    "path": path,
                    "message": f"cron 文件内容变更: {path}",
                }
            )
    for path in previous:
        if path not in current:
            events.append(
                {
                    "type": "计划任务删除",
                    "level": "中",
                    "path": path,
                    "message": f"cron 文件消失: {path}",
                }
            )
    return events

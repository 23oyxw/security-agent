#!/usr/bin/env python3
"""终端告警监视 — 后台 Streamlit 运行时，在普通终端里也能看到高/严重事件.

用法:
  cd /path/to/security-agent
  uv run python scripts/alert_watch.py

可选环境变量:
  NOTIFY_DESKTOP=true   与 Web 端相同，尝试 notify-send 弹窗
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from security_agent import config  # noqa: E402
from security_agent.notify.alerts import format_alert_line  # noqa: E402

EVENTS_FILE = config.DATA_DIR / "alerts" / "events.jsonl"


def _color_line(line: str, level: str) -> str:
    if level == "严重":
        return f"\033[1;31m{line}\033[0m"
    if level == "高":
        return f"\033[1;33m{line}\033[0m"
    return line


def tail_forever() -> None:
    config.ensure_data_dirs()
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not EVENTS_FILE.exists():
        EVENTS_FILE.touch()

    print("=" * 60)
    print(" 安全运维 Agent — 终端告警监视")
    print(f" 文件: {EVENTS_FILE}")
    print(" 说明: 请保持本窗口打开；Web 后台监控触发 严重/高 事件会打印在此")
    print(" 退出: Ctrl+C")
    print("=" * 60)

    with EVENTS_FILE.open("r", encoding="utf-8") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                print(line)
                continue
            text = format_alert_line(ev)
            print(_color_line(text, str(ev.get("level", ""))), flush=True)


def main() -> int:
    try:
        tail_forever()
    except KeyboardInterrupt:
        print("\n[alert_watch] 已退出")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

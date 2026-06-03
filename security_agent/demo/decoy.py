#!/usr/bin/env python3
"""安全诱饵进程 — 命令行含高危工具名，实际仅 sleep，供扫描/监控演练."""

from __future__ import annotations

import argparse
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Security agent risk decoy (safe hold process)")
    parser.add_argument("--hold", action="store_true", help="保持运行直至被终止")
    parser.add_argument(
        "--simulate-tool",
        default="nmap",
        choices=("nmap", "nc", "ncat", "hydra", "sqlmap", "masscan"),
        help="仅在 argv 中出现该名称以触发规则，不执行该工具",
    )
    parser.add_argument("--seconds", type=int, default=3600)
    args = parser.parse_args()
    if not args.hold:
        parser.print_help()
        return
    # 进程真实行为：休眠；高危名仅出现在 ps 命令行参数中
    time.sleep(max(1, args.seconds))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""定时巡检脚本 — 供 Cron 调用，执行健康巡检 + 日志扫描 + 配置变更检测.

用法:
  # 每 30 分钟健康巡检
  */30 * * * *  cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py healthcheck

  # 每 6 小时安全加固扫描
  0 */6 * * *   cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py hardening

  # 每天凌晨 2 点生成日报
  0 2 * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py daily_report

  # 每小时配置变更检测
  0 * * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py config_diff

  # 增量日志扫描（每 15 分钟）
  */15 * * * *  cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py log_scan

  # 全量巡检（每天一次）
  0 6 * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py full
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from security_agent import config
from security_agent.timeutil import now_iso

REPORT_DIR = config.DATA_DIR / "patrol_reports"


def save_report(task: str, result: dict) -> Path:
    """保存巡检报告到 data/patrol_reports/."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{task}_{ts}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # 更新 latest
    latest = REPORT_DIR / f"{task}_latest.json"
    latest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_healthcheck() -> dict:
    """健康巡检."""
    from security_agent.skills.healthcheck.skill import HealthCheckSkill

    skill = HealthCheckSkill()
    snap = skill.take_snapshot()
    result = {
        "task": "healthcheck",
        "ts": now_iso(),
        "snapshot": snap.to_dict(),
        "status": "告警" if snap.alerts else "正常",
    }
    # 趋势分析
    if len(skill._history) >= 2:
        for metric in ("cpu", "memory", "disk"):
            trend = skill.analyze_trend(metric, last_n=min(20, len(skill._history)))
            result[f"{metric}_trend"] = trend
    return result


def run_hardening() -> dict:
    """安全加固扫描."""
    from security_agent.skills.security_hardening.skill import SecurityHardeningSkill

    skill = SecurityHardeningSkill()
    return {
        "task": "hardening",
        "ts": now_iso(),
        "result": skill.full_scan(),
    }


def run_log_scan() -> dict:
    """增量日志扫描."""
    from security_agent.skills.log_analyzer.skill import LogAnalyzerSkill

    skill = LogAnalyzerSkill()
    matches = skill.incremental_scan()
    return {
        "task": "log_scan",
        "ts": now_iso(),
        "new_matches": len(matches),
        "matches": [m.to_dict() for m in matches],
        "status": "告警" if any(m.severity in ("严重", "高") for m in matches) else "正常",
    }


def run_config_diff() -> dict:
    """配置变更检测."""
    from security_agent.skills.config_manager.skill import ConfigManagerSkill

    skill = ConfigManagerSkill()
    # 先确保有基线快照
    latest = config.DATA_DIR / "config_snapshots" / "latest.json"
    if not latest.exists():
        skill.take_snapshot()
        return {
            "task": "config_diff",
            "ts": now_iso(),
            "action": "baseline_created",
            "message": "首次运行，已创建基线快照",
        }

    changes = skill.diff_current_vs_snapshot()
    if changes:
        # 更新快照
        skill.take_snapshot()
    return {
        "task": "config_diff",
        "ts": now_iso(),
        "changes": len(changes),
        "details": changes,
        "status": "告警" if changes else "正常",
    }


def run_daily_report() -> dict:
    """每日综合报告."""
    health = run_healthcheck()
    hardening = run_hardening()
    log_scan = run_log_scan()
    config_diff = run_config_diff()

    # 汇总告警数
    alerts = []
    if health.get("status") == "告警":
        alerts.extend(health["snapshot"].get("alerts", []))
    if log_scan.get("status") == "告警":
        alerts.append(f"发现 {log_scan['new_matches']} 条新异常日志")
    if config_diff.get("status") == "告警":
        alerts.append(f"检测到 {config_diff['changes']} 处配置变更")

    # 基线合规率
    baseline = hardening.get("result", {}).get("baseline_check", {})
    compliance_rate = baseline.get("compliance_rate", 0)

    return {
        "task": "daily_report",
        "ts": now_iso(),
        "summary": {
            "health_status": health.get("status"),
            "cpu": health.get("snapshot", {}).get("cpu_percent"),
            "memory": health.get("snapshot", {}).get("memory_percent"),
            "disk": health.get("snapshot", {}).get("disk_percent"),
            "compliance_rate": compliance_rate,
            "log_alerts": log_scan.get("new_matches", 0),
            "config_changes": config_diff.get("changes", 0),
            "total_alerts": len(alerts),
            "alerts": alerts,
        },
        "health": health,
        "hardening_summary": {
            "ssh_issues": hardening.get("result", {}).get("ssh_audit", {}).get("issue_count"),
            "fw_type": hardening.get("result", {}).get("firewall_audit", {}).get("firewall_type"),
            "vuln_count": hardening.get("result", {}).get("vulnerability_scan", {}).get("total_issues"),
            "compliance_rate": compliance_rate,
        },
        "log_scan": log_scan,
        "config_diff": config_diff,
    }


def run_full() -> dict:
    """全量巡检（所有项目）."""
    result = run_daily_report()
    result["task"] = "full"
    return result


TASKS = {
    "healthcheck": run_healthcheck,
    "hardening": run_hardening,
    "log_scan": run_log_scan,
    "config_diff": run_config_diff,
    "daily_report": run_daily_report,
    "full": run_full,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="安全运维 Agent 定时巡检脚本")
    parser.add_argument(
        "task",
        choices=list(TASKS.keys()),
        help="巡检任务类型",
    )
    parser.add_argument("--quiet", action="store_true", help="静默模式（仅输出文件路径）")
    args = parser.parse_args()

    try:
        result = TASKS[args.task]()
        path = save_report(args.task, result)

        if args.quiet:
            print(str(path))
        else:
            print(f"[{args.task}] 巡检完成 — {result.get('status', 'OK')}")
            print(f"  报告: {path}")

            # 打印关键摘要
            if args.task == "healthcheck":
                snap = result.get("snapshot", {})
                print(f"  CPU={snap.get('cpu_percent')}% Memory={snap.get('memory_percent')}% Disk={snap.get('disk_percent')}%")
                if snap.get("alerts"):
                    for a in snap["alerts"]:
                        print(f"  ⚠️  {a}")

            elif args.task == "log_scan":
                print(f"  新匹配: {result.get('new_matches', 0)}")
                for m in result.get("matches", [])[:5]:
                    print(f"  [{m.get('severity')}] {m.get('pattern_name')}: {m.get('matched_text', '')[:80]}")

            elif args.task == "config_diff":
                print(f"  变更: {result.get('changes', 0)}")
                for c in result.get("details", [])[:5]:
                    print(f"  [{c.get('severity')}] {c.get('path')}: {c.get('change')}")

            elif args.task == "daily_report":
                s = result.get("summary", {})
                print(f"  健康: {s.get('health_status')} | 合规: {s.get('compliance_rate')}% | 日志告警: {s.get('log_alerts')} | 配置变更: {s.get('config_changes')}")
                if s.get("alerts"):
                    for a in s["alerts"][:5]:
                        print(f"  ⚠️  {a}")

        return 0 if result.get("status", "正常") != "告警" else 1

    except Exception as exc:
        print(f"[{args.task}] 巡检失败: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
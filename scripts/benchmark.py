#!/usr/bin/env python3
"""统一基准跑分框架 — 消除散乱分布，建立统一指标.

解决问题:
    1. 单次测试偏移 (flaky detection) — 对比历史记录，标记波动 > 10% 的套件
    2. 散乱分布 — 一键跑全部，统一报告格式
    3. 无统一指标 — 每套件的 pass/fail/time 统一采集

用法:
    python scripts/benchmark.py              # 跑全部
    python scripts/benchmark.py --quick      # 快速模式 (只跑核心)
    python scripts/benchmark.py --history    # 查看历史趋势
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "benchmark_history.jsonl"

# 测试套件定义: (名称, 路径, 权重)
SUITES: list[dict[str, Any]] = [
    {
        "name": "sandbox",
        "path": "tests/test_sandbox_overlay.py",
        "step": 1,
        "description": "全域沙箱透明化",
        "weight": 1.0,
    },
    {
        "name": "alerts",
        "path": "tests/test_alert_throttle.py",
        "step": 2,
        "description": "告警安静化",
        "weight": 1.0,
    },
    {
        "name": "terminal",
        "path": "tests/test_terminal_context.py",
        "step": 3,
        "description": "终端智能化",
        "weight": 1.0,
    },
    {
        "name": "document",
        "path": "tests/test_document_pipeline.py",
        "step": 4,
        "description": "文档活化",
        "weight": 1.0,
    },
    {
        "name": "boundary",
        "path": "tests/test_boundary_fuzzer.py",
        "step": 5,
        "description": "边界自检化",
        "weight": 1.0,
    },
]

QUICK_SUITES = [
    {"name": "contract", "command": [sys.executable, str(ROOT / "scripts/verify_triple_unify.py")], "step": 0},
    {"name": "version", "command": [sys.executable, str(ROOT / "scripts/check_version.py")], "step": 0},
]


def run_suite(suite: dict[str, Any]) -> dict[str, Any]:
    """运行单个测试套件并返回指标."""
    t0 = time.time()
    path = ROOT / suite["path"]

    result = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=str(ROOT),
    )

    elapsed = round(time.time() - t0, 2)
    output = result.stdout + result.stderr

    # 从输出中提取 pass/fail 计数（只计数单行测试结果）
    passed, failed = 0, 0
    for line in output.splitlines():
        line_stripped = line.strip()
        # 只匹配单行测试结果：  PASS xxx 或   FAIL xxx
        if line_stripped.startswith("PASS ") and not line_stripped.startswith("PASS -"):
            passed += 1
        elif line_stripped.startswith("FAIL ") and not line_stripped.startswith("FAIL -"):
            failed += 1

    # 如果没匹配到（可能用了不同的输出格式），从 "Results: X/Y" 提取
    if passed == 0 and failed == 0:
        for line in output.splitlines():
            if "Results:" in line and "/" in line:
                try:
                    parts = line.split()
                    nums = [p for p in parts if "/" in p][0]
                    passed = int(nums.split("/")[0])
                    failed = int(nums.split("/")[1].split()[0])
                except (ValueError, IndexError):
                    pass

    total = passed + failed
    pass_rate = round(passed / total, 4) if total > 0 else 1.0

    return {
        "suite": suite["name"],
        "step": suite["step"],
        "description": suite.get("description", ""),
        "passed": passed,
        "failed": failed,
        "total": total,
        "pass_rate": pass_rate,
        "elapsed_sec": elapsed,
        "weight": suite.get("weight", 1.0),
        "exit_code": result.returncode,
    }


def run_quick() -> list[dict[str, Any]]:
    """快速验证: 只跑契约+版本检查."""
    results = []
    for q in QUICK_SUITES:
        t0 = time.time()
        try:
            r = subprocess.run(
                q["command"],
                capture_output=True, text=True, timeout=30, cwd=str(ROOT),
            )
            ok = r.returncode == 0
            results.append({
                "suite": q["name"],
                "step": q["step"],
                "passed": 1 if ok else 0,
                "failed": 0 if ok else 1,
                "total": 1,
                "pass_rate": 1.0 if ok else 0.0,
                "elapsed_sec": round(time.time() - t0, 2),
            })
        except Exception:
            results.append({
                "suite": q["name"],
                "passed": 0, "failed": 1, "total": 1,
                "pass_rate": 0.0, "elapsed_sec": 0,
            })
    return results


def compute_score(results: list[dict[str, Any]]) -> dict[str, Any]:
    """计算加权综合分."""
    total_weight = sum(r.get("weight", 1.0) for r in results)
    weighted_pass_rate = sum(
        r["pass_rate"] * r.get("weight", 1.0) for r in results
    ) / max(total_weight, 1)

    total_tests = sum(r["total"] for r in results)
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_time = sum(r["elapsed_sec"] for r in results)

    # 健康度: 全部通过 = 1.0, 有失败按加权扣分
    health = weighted_pass_rate

    return {
        "total_suites": len(results),
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "weighted_pass_rate": round(weighted_pass_rate, 4),
        "total_elapsed_sec": round(total_time, 2),
        "health_score": round(health * 100, 1),
        "verdict": "PASS" if total_failed == 0 else "FAIL",
    }


def detect_drift(current: dict[str, Any], history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检测偏离: 对比历史均值，标记波动超过阈值的套件."""
    if len(history) < 2:
        return []

    drifts = []
    for suite_result in current.get("suites", []):
        name = suite_result["suite"]
        hist_rates = [
            h["suites_map"].get(name, {}).get("pass_rate", 0)
            for h in history[-5:]  # 最近 5 次
            if "suites_map" in h
        ]
        if len(hist_rates) < 2:
            continue

        hist_mean = sum(hist_rates) / len(hist_rates)
        current_rate = suite_result["pass_rate"]
        deviation = abs(current_rate - hist_mean)

        if deviation > 0.1:  # 波动超过 10%
            drifts.append({
                "suite": name,
                "current_rate": current_rate,
                "historical_mean": round(hist_mean, 4),
                "deviation": round(deviation, 4),
                "direction": "improved" if current_rate > hist_mean else "degraded",
            })

    return drifts


def save_history(report: dict[str, Any]) -> None:
    """保存基准结果到历史文件."""
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "score": report["score"],
        "suites_map": {
            s["suite"]: {
                "passed": s["passed"],
                "failed": s["failed"],
                "total": s["total"],
                "pass_rate": s["pass_rate"],
                "elapsed_sec": s["elapsed_sec"],
            }
            for s in report["suites"]
        },
    }
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_history(limit: int = 20) -> list[dict[str, Any]]:
    """加载历史记录."""
    if not HISTORY_PATH.exists():
        return []
    records = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records[-limit:]


def print_report(report: dict[str, Any]) -> None:
    """打印统一基准报告."""
    score = report["score"]
    suites = report["suites"]
    drifts = report.get("drifts", [])

    print()
    print("=" * 68)
    print("  SECURITY-AGENT  UNIFIED BENCHMARK")
    print("=" * 68)
    print(f"  Time:  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Score: {score['health_score']:.1f}/100  [{score['verdict']}]")
    print(f"  Tests: {score['total_tests']} total  |  "
          f"{score['total_passed']} passed  |  "
          f"{score['total_failed']} failed")
    print(f"  Rate:  {score['weighted_pass_rate']:.2%}")
    print(f"  Time:  {score['total_elapsed_sec']}s total")
    print("-" * 68)

    # 每套件明细
    col_name = 14
    col_desc = 16
    col_res = 14
    col_time = 10
    print(f"  {'Suite':<{col_name}} {'Description':<{col_desc}} {'Result':<{col_res}} {'Time':<{col_time}}")
    print(f"  {'-'*col_name} {'-'*col_desc} {'-'*col_res} {'-'*col_time}")
    for s in suites:
        name = s["suite"]
        desc = s.get("description", "")[:col_desc-1]
        res = f"{s['passed']}/{s['total']} ({s['pass_rate']:.0%})"
        elapsed = f"{s['elapsed_sec']}s"
        marker = "  OK" if s["failed"] == 0 else "  !!FAIL"
        print(f"  {name:<{col_name}} {desc:<{col_desc}} {res:<{col_res}} {elapsed:<{col_time}}{marker}")

    # 偏离检测
    if drifts:
        print("-" * 68)
        print("  DRIFT DETECTED:")
        for d in drifts:
            arrow = "UP" if d["direction"] == "improved" else "DOWN"
            print(f"  {d['suite']}: {d['historical_mean']:.2%} -> {d['current_rate']:.2%}"
                  f" (deviation={d['deviation']:.2%}, {arrow})")

    print("=" * 68)

    # 进度条
    completed = sum(1 for s in suites if s["failed"] == 0)
    total_steps = 6
    bar = "".join("#" if i < completed else "." for i in range(total_steps))
    print(f"  Steps: [{bar}] {completed}/{total_steps}")
    print()


def main() -> None:
    quick = "--quick" in sys.argv
    show_history = "--history" in sys.argv

    if show_history:
        records = load_history(20)
        if not records:
            print("No benchmark history found.")
            return
        print(f"Last {len(records)} benchmark runs:")
        for r in records[-10:]:
            s = r["score"]
            print(f"  {r['timestamp']}  score={s['health_score']:.0f}  "
                  f"{s['total_passed']}/{s['total_tests']} passed  "
                  f"verdict={s['verdict']}")
        return

    if quick:
        suites_results = run_quick()
    else:
        suites_results = [run_suite(s) for s in SUITES]

    score = compute_score(suites_results)
    history = load_history(10)

    report = {
        "suites": suites_results,
        "score": score,
        "drifts": [],
    }

    # 偏离检测
    if len(history) >= 2:
        current = {"suites": suites_results, "score": score}
        report["drifts"] = detect_drift(current, history)

    print_report(report)
    save_history(report)


if __name__ == "__main__":
    main()

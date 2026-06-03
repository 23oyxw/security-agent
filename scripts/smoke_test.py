#!/usr/bin/env python3
"""Runtime smoke tests — no API key required for most checks."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


def test_imports() -> None:
    try:
        import security_agent  # noqa: F401
        import streamlit  # noqa: F401
        from security_agent.agent.brain import AgentBrain
        from security_agent.scanner.engine import run_security_scan, block_process, list_processes
        from security_agent.tools.registry import TOOL_REGISTRY, call_tool_local
        record("Python 模块导入", True, f"tools={len(TOOL_REGISTRY)}")
    except Exception as exc:
        record("Python 模块导入", False, str(exc))


def test_scanner() -> None:
    from security_agent.scanner.engine import run_security_scan, format_security_report, list_processes

    data = run_security_scan()
    ok = "risks" in data and "scanned_at" in data
    record("安全扫描", ok, f"风险数={data.get('risk_count', '?')}")
    report = format_security_report(data)
    record("扫描报告格式化", isinstance(report, str) and len(report) > 0)
    procs = list_processes(limit=5)
    record("进程列表", isinstance(procs, list) and len(procs) > 0, f"样本={len(procs)}")


def test_tools() -> None:
    from security_agent.tools.registry import TOOL_REGISTRY, call_tool_local

    async def run_all():
        # 确保 Skill 工具已加载（避免迭代时字典变化）
        from security_agent.skills.registry import auto_discover, merge_skill_tools_into_registry
        auto_discover()
        merge_skill_tools_into_registry()
        skip = {"block_high_risk_process"}
        for name in list(TOOL_REGISTRY):
            if name in skip:
                record(f"工具:{name}", True, "跳过（需真实 PID）")
                continue
            try:
                out = await call_tool_local(name, {})
                if out.startswith("工具执行失败") or out.startswith("未知工具"):
                    record(f"工具:{name}", False, out[:80])
                else:
                    record(f"工具:{name}", True, out[:60].replace("\n", " "))
            except Exception as exc:
                record(f"工具:{name}", False, str(exc))

    asyncio.run(run_all())


def test_monitor() -> None:
    from security_agent.monitor import get_monitor_service

    svc = get_monitor_service()
    msg1 = svc.start()
    running = svc.running
    events = svc.get_events(10)
    msg2 = svc.stop()
    record("监控启停", running and "启动" in msg1, f"{msg1} / {msg2}")
    record("监控事件缓冲", isinstance(events, list))


def test_audit() -> None:
    from security_agent.audit.log import append_audit, read_audit_tail

    append_audit("smoke_test", {"ok": True})
    rows = read_audit_tail(5)
    record("审计日志", any(r.get("action") == "smoke_test" for r in rows), f"条目={len(rows)}")


def test_report() -> None:
    from security_agent.scanner.engine import run_security_scan, generate_html_report

    data = run_security_scan()
    path = generate_html_report(data)
    ok = Path(path).exists() and Path(path).stat().st_size > 100
    record("HTML 报告生成", ok, path)


def test_redact() -> None:
    from security_agent.security.redact import redact_text

    cases = [
        ("password=Secret123", "***" in redact_text("password=Secret123")),
        ("sk-abcdef1234567890", "sk-" in redact_text("sk-abcdef1234567890") and "abcdef1234567890" not in redact_text("sk-abcdef1234567890")),
        ("Failed password for root from 10.0.0.1", "root" not in redact_text("Failed password for root from 10.0.0.1") or "***" in redact_text("Failed password for root from 10.0.0.1")),
    ]
    ok = all(c[1] for c in cases)
    record("敏感信息打码", ok, str([c[0][:30] for c in cases]))


def test_monitor_p2() -> None:
    from security_agent.monitor.listen_watch import diff_listeners, snapshot_listeners
    from security_agent.monitor.cron_watch import collect_cron_signatures

    snap = snapshot_listeners()
    record("P2-监听快照", isinstance(snap, dict))
    record("P2-cron签名", isinstance(collect_cron_signatures(), dict))
    d = diff_listeners({}, {("0.0.0.0", 59999): {"port": 59999, "local": "0.0.0.0:59999", "pid": 1}})
    record("P2-监听diff", len(d) == 1)


def test_demo() -> None:
    from security_agent.demo.boundary import run_terminal_boundary_tests, summarize_boundary
    from security_agent.demo.evaluator import run_detection_calibration
    from security_agent.demo.fixture_catalog import DETECTION_FIXTURES
    from security_agent.demo.service import get_demo_service

    rows = run_terminal_boundary_tests()
    summary = summarize_boundary(rows)
    record("风险演练-边界", summary["failed"] == 0, f"{summary['passed']}/{summary['total']}")
    cal = run_detection_calibration()
    cs = cal["summary"]
    record(
        "风险演练-校准66例",
        cs["failed"] == 0 and cs["total"] == len(DETECTION_FIXTURES),
        f"{cs['passed']}/{cs['total']} acc={cs['accuracy_pct']}%",
    )
    svc = get_demo_service()
    syn = svc.build_synthetic_scan()
    record("风险演练-合成", syn.get("risk_count", 0) >= 3, f"风险={syn.get('risk_count')}")


def test_policy() -> None:
    from security_agent.agent.policy import summarize_risks, should_auto_warn

    risks = [{"level": "严重", "type": "高危进程"}]
    record("风险策略", should_auto_warn(risks) and summarize_risks(risks)["严重"] == 1)


def test_api_key_config() -> None:
    from security_agent import config

    ok = bool(config.DEEPSEEK_API_KEY) and config.DEEPSEEK_API_KEY not in (
        "your_key_here",
        "sk-your-key-here",
    )
    env_path = ROOT / ".env"
    record(
        "API Key 配置",
        ok,
        "已配置 .env" if ok else f"未配置（请编辑 .env 后 boot_start） env_file={env_path.exists()}",
    )


async def test_agent_chat() -> None:
    from security_agent import config
    from security_agent.agent.brain import AgentBrain

    if not config.DEEPSEEK_API_KEY:
        record("Agent 对话", False, "跳过：无 API Key")
        return
    try:
        brain = AgentBrain()
        result = await brain.chat("用一句话说明你能做什么，不要调用工具。")
        reply = result.get("reply", "")
        record("Agent 对话", bool(reply) and len(reply) > 5, reply[:80].replace("\n", " "))
    except Exception as exc:
        record("Agent 对话", False, str(exc))


async def test_mcp() -> None:
    try:
        from security_agent.knowledge.mcp.client import MCPToolExecutor
    except ImportError as exc:
        record("MCP 连接与调用", False, f"跳过: {exc}")
        return

    client = MCPToolExecutor()
    try:
        names = await client.connect()
        out = await client.call_tool("query_security_scan", {})
        record("MCP 连接与调用", "query_security_scan" in names and len(out) > 0, f"tools={len(names)}")
    except Exception as exc:
        record("MCP 连接与调用", False, str(exc))
    finally:
        await client.close()


def test_skill_flows() -> None:
    from security_agent.skills.flows import list_flows, run_skill_flow
    from security_agent.agent.orchestrator import detect_intent, build_plan

    flows = list_flows()
    record("L2 flow 列表", len(flows) >= 3, f"count={len(flows)}")
    record("意图→scan_report", detect_intent("生成扫描报告") == "scan_report")
    record("plan.skill_flow", build_plan("一键扫描报告").get("skill_flow") == "scan_report")

    async def run():
        return await run_skill_flow("scan_report", {})

    result = asyncio.run(run())
    record("L2 scan_report 执行", result.get("ok") is True, result.get("trace_id", ""))


def test_mac_checker() -> None:
    from security_agent.safety_gate.mac_checker import get_mac_checker
    from security_agent.terminal.executor import run_readonly_sync

    mac = get_mac_checker(enforce=False)
    chk = mac.pre_exec_check("terminal.exec", {"command": "echo ok"}, "READONLY")
    record("MAC pre_exec_check", chk.allowed, chk.reason[:80])
    tr = run_readonly_sync("ps aux | head -3")
    record("终端+MAC 钩子", tr.ok, tr.message[:60])


def test_api_e2e() -> None:
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "e2e_api_smoke.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    record("API E2E 脚本", proc.returncode == 0, proc.stdout.splitlines()[-1] if proc.stdout else proc.stderr[:120])


def test_scripts() -> None:
    import os

    scripts = ["boot_start.sh", "boot_stop.sh"]
    missing = [s for s in scripts if not (ROOT / s).exists()]
    not_exec = [s for s in scripts if (ROOT / s).exists() and not os.access(ROOT / s, os.X_OK)]
    ok = not missing and not not_exec
    detail = f"missing={missing} not_exec={not_exec}" if not ok else "齐全且可执行"
    record("启动脚本", ok, detail)


def main() -> int:
    import os

    print("=== 安全运维 Agent 功能冒烟测试 ===\n")
    test_imports()
    test_scanner()
    test_tools()
    test_monitor()
    test_audit()
    test_report()
    test_redact()
    test_monitor_p2()
    test_demo()
    test_policy()
    test_api_key_config()
    test_skill_flows()
    test_mac_checker()
    test_api_e2e()
    test_scripts()
    print()
    asyncio.run(test_agent_chat())
    asyncio.run(test_mcp())
    print()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    failed = [(n, d) for n, ok, d in RESULTS if not ok]
    print(f"=== 结果: {passed}/{total} 通过 ===")
    if failed:
        print("\n未通过项:")
        for n, d in failed:
            print(f"  - {n}: {d}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

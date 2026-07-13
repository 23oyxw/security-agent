"""边界韧性测试 — 探针网格 + 模糊测试."""

from __future__ import annotations

import sys


# ---- ProbeGrid ----

def test_probe_grid_defines_12_probes():
    """定义了 12 根探针."""
    from security_agent.sandbox.probes import ProbeGrid
    grid = ProbeGrid()
    probes = grid.list_probes()
    assert len(probes) == 12, f"Expected 12, got {len(probes)}"


def test_probe_categories():
    """三类探针各有 4 根."""
    from security_agent.sandbox.probes import ProbeGrid
    grid = ProbeGrid()
    cats = grid.categories()
    assert cats["privilege"] == 4
    assert cats["filesystem"] == 4
    assert cats["network"] == 4


def test_probe_patrol_runs():
    """巡检不崩溃."""
    from security_agent.sandbox.probes import ProbeGrid
    grid = ProbeGrid()
    report = grid.run_all_patrol(timeout_per_probe=5.0)
    assert report.total == 12
    assert report.passed + report.failed == 12


def test_probe_patrol_report_to_dict():
    """巡检报告可序列化."""
    from security_agent.sandbox.probes import ProbeGrid
    grid = ProbeGrid()
    report = grid.run_all_patrol(timeout_per_probe=5.0)
    d = report.to_dict()
    assert "findings" in d
    assert "health_score" in d
    assert "summary" in d
    assert len(d["findings"]) == 12


def test_probe_patrol_health_score():
    """health_score 范围正确."""
    from security_agent.sandbox.probes import ProbeGrid
    grid = ProbeGrid()
    report = grid.run_all_patrol(timeout_per_probe=5.0)
    assert 0.0 <= report.health_score <= 1.0


def test_probe_run_category():
    """单类巡检."""
    from security_agent.sandbox.probes import ProbeGrid
    grid = ProbeGrid()
    report = grid.run_category("privilege")
    assert report.total == 4


def test_probe_finding_to_dict():
    """ProbeFinding 可序列化."""
    from security_agent.sandbox.probes import ProbeGrid
    grid = ProbeGrid()
    report = grid.run_category("filesystem")
    for f in report.findings:
        d = f.to_dict()
        assert "probe_id" in d
        assert "passed" in d
        assert "severity" in d


# ---- BoundaryFuzzer ----

def test_fuzzer_strategies():
    """7 种策略全部定义."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    assert len(fuzzer.STRATEGIES) == 7
    assert "path_traversal" in fuzzer.STRATEGIES
    assert "command_injection" in fuzzer.STRATEGIES


def test_fuzzer_generates_mutations():
    """生成变异."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    result = fuzzer.fuzz("ls /tmp", rounds=20, intensity="normal")
    assert result.rounds == 20
    assert result.mutations_generated > 0
    assert result.health > 0


def test_fuzzer_result_to_dict():
    """FuzzResult 可序列化."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    result = fuzzer.fuzz("echo hello", rounds=5)
    d = result.to_dict()
    for key in ("rounds", "mutations_generated", "penetrations", "health", "summary"):
        assert key in d, f"Missing key: {key}"


def test_fuzzer_no_penetration_on_safe_cmd():
    """安全命令不应该产生穿透."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    result = fuzzer.fuzz("echo test_safe", rounds=10, intensity="aggressive")
    # echo 命令的变异不应该能读取敏感文件
    assert result.health >= 0.5, f"Unexpected low health: {result.summary}"


def test_fuzzer_stats():
    """stats() 返回统计."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    fuzzer.fuzz("ls /tmp", rounds=5)
    stats = fuzzer.stats()
    assert "total_penetrations" in stats
    assert "strategies" in stats
    assert len(stats["strategies"]) == 7


def test_fuzzer_history():
    """history() 追踪穿透."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    fuzzer.fuzz("cat /etc/hostname", rounds=10, intensity="aggressive")
    history = fuzzer.history()
    assert isinstance(history, list)


# ---- 路径穿越专项 ----

def test_path_traversal_mutation():
    """路径穿越策略生成变异."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    mutated = fuzzer._apply_strategy("cat /var/log/messages", "path_traversal")
    assert mutated is not None
    assert "etc" in mutated or "shadow" in mutated


def test_command_injection_mutation():
    """命令注入策略生成变异."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    mutated = fuzzer._apply_strategy("ls /tmp", "command_injection")
    assert len(mutated) > len("ls /tmp")


def test_whitespace_bypass_mutation():
    """空白符绕过."""
    from security_agent.sandbox.fuzzer import BoundaryFuzzer
    fuzzer = BoundaryFuzzer()
    mutated = fuzzer._apply_strategy("ls /tmp", "whitespace_bypass")
    assert "${IFS}" in mutated


# ---- 运行入口 ----

if __name__ == "__main__":
    import traceback

    tests = [
        ("test_probe_grid_defines_12_probes", test_probe_grid_defines_12_probes),
        ("test_probe_categories", test_probe_categories),
        ("test_probe_patrol_runs", test_probe_patrol_runs),
        ("test_probe_patrol_report_to_dict", test_probe_patrol_report_to_dict),
        ("test_probe_patrol_health_score", test_probe_patrol_health_score),
        ("test_probe_run_category", test_probe_run_category),
        ("test_probe_finding_to_dict", test_probe_finding_to_dict),
        ("test_fuzzer_strategies", test_fuzzer_strategies),
        ("test_fuzzer_generates_mutations", test_fuzzer_generates_mutations),
        ("test_fuzzer_result_to_dict", test_fuzzer_result_to_dict),
        ("test_fuzzer_no_penetration_on_safe_cmd", test_fuzzer_no_penetration_on_safe_cmd),
        ("test_fuzzer_stats", test_fuzzer_stats),
        ("test_fuzzer_history", test_fuzzer_history),
        ("test_path_traversal_mutation", test_path_traversal_mutation),
        ("test_command_injection_mutation", test_command_injection_mutation),
        ("test_whitespace_bypass_mutation", test_whitespace_bypass_mutation),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
            passed += 1
        except Exception:
            print(f"  FAIL {name}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{len(tests)} passed ({failed} failed)")
    if failed == 0:
        print("  ALL PASS - Boundary resilience verified!")
    print(f"{'='*60}")

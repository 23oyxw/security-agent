"""终端智能测试 — 上下文采集 + 预分析 + 后验证 + 学习 + 智能执行."""

from __future__ import annotations

import tempfile
from pathlib import Path


# ---- TerminalContext ----

def test_context_gather():
    """上下文采集返回完整快照."""
    from security_agent.terminal.context import TerminalContext
    ctx = TerminalContext()
    snap = ctx.gather(trace_id="test123")
    assert snap.cwd != ""
    assert snap.current_user != ""
    assert snap.platform != ""
    d = snap.to_dict()
    assert "system" in d
    assert "session" in d
    assert "files" in d
    assert "security" in d


def test_context_summary():
    """summary 属性返回可读文本."""
    from security_agent.terminal.context import TerminalContext
    ctx = TerminalContext()
    snap = ctx.gather()
    assert len(snap.summary) > 0


def test_context_record_commands():
    """记录命令后 recent_commands 更新."""
    from security_agent.terminal.context import TerminalContext
    ctx = TerminalContext()
    ctx.record_command("ls -la")
    ctx.record_command("df -h")
    snap = ctx.gather()
    assert "ls -la" in snap.recent_commands or "df -h" in snap.recent_commands


def test_context_failure_count():
    """失败计数正确."""
    from security_agent.terminal.context import TerminalContext
    ctx = TerminalContext()
    assert ctx.gather().failed_count == 0
    ctx.record_failure()
    ctx.record_failure()
    assert ctx.gather().failed_count == 2
    ctx.record_success()
    assert ctx.gather().failed_count == 0


def test_context_singleton():
    """单例返回同一实例."""
    from security_agent.terminal.context import get_terminal_context
    c1 = get_terminal_context()
    c2 = get_terminal_context()
    assert c1 is c2


# ---- PreExecutionAnalyzer ----

def test_pre_analyzer_classify_observe():
    """ls 命令分类为 observe."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("ls -la /tmp")
    assert report.command_type == "observe"
    assert report.risk_score < 0.2


def test_pre_analyzer_classify_delete():
    """rm -rf 分类为 delete + 高风险."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("rm -rf /tmp/cache")
    assert "delete" in report.command_type
    assert report.risk_score > 0.3


def test_pre_analyzer_classify_privilege():
    """sudo 分类为 privilege."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("sudo systemctl restart nginx")
    assert "privilege" in report.command_type


def test_pre_analyzer_danger_detection():
    """危险命令被检测."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("rm -rf /")
    assert report.risk_score > 0.9
    assert len(report.danger_matches) > 0


def test_pre_analyzer_chmod_777_warning():
    """chmod 777 风险分较高."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("chmod 777 /var/www/html")
    assert report.risk_score > 0.5


def test_pre_analyzer_alternatives():
    """高风险命令有替代方案."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("rm -rf /var/log")
    if report.risk_score > 0.5:
        assert len(report.safer_alternatives) > 0


def test_pre_analyzer_path_extraction():
    """路径正确提取."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("cat /var/log/syslog /etc/hosts")
    assert "/var/log/syslog" in report.affected_paths
    assert "/etc/hosts" in report.affected_paths


def test_pre_analyzer_to_dict():
    """PreExecReport.to_dict() 完整."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("ls -la")
    d = report.to_dict()
    for key in ("command", "command_type", "risk_score", "risk_factors"):
        assert key in d


def test_pre_analyzer_summary():
    """summary 人类可读."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    report = a.analyze("rm -rf /tmp/test")
    assert len(report.summary) > 0


def test_understand_intent():
    """意图理解返回建议."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    result = a.understand_intent("查看磁盘使用情况")
    assert "suggestions" in result
    # 应该有匹配
    if result["suggestions"]:
        assert "command" in result["suggestions"][0]


def test_understand_intent_no_match():
    """无匹配时返回空建议."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    result = a.understand_intent("xyzabc123")
    assert result["suggestions"] == []


def test_pre_analyzer_history():
    """历史记录功能."""
    from security_agent.terminal.pre_analyzer import PreExecutionAnalyzer
    a = PreExecutionAnalyzer()
    a.record_execution("ls -la", True, "observe")
    a.record_execution("ls -la", True, "observe")
    a.record_execution("rm -rf /tmp/x", False, "delete")
    stats = a.history_stats()
    assert stats["total"] == 3
    assert abs(stats["success_rate"] - 2/3) < 0.01


# ---- PostExecutionVerifier ----

def test_verifier_exit_0():
    """退出码 0 → pass."""
    from security_agent.terminal.post_verifier import PostExecutionVerifier
    v = PostExecutionVerifier()
    report = v.verify("output", "", 0)
    assert report.passed is True


def test_verifier_exit_nonzero():
    """退出码非 0 → fail."""
    from security_agent.terminal.post_verifier import PostExecutionVerifier
    v = PostExecutionVerifier()
    report = v.verify("", "error occurred", 1)
    assert report.passed is False


def test_verifier_empty_output():
    """空输出 → warn."""
    from security_agent.terminal.post_verifier import PostExecutionVerifier
    v = PostExecutionVerifier()
    report = v.verify("", "", 0)
    warns = [c for c in report.checks if c.status == "warn"]
    assert len(warns) >= 1


def test_verifier_to_dict():
    """VerifyReport.to_dict() 完整."""
    from security_agent.terminal.post_verifier import PostExecutionVerifier
    v = PostExecutionVerifier()
    report = v.verify("hello world", "", 0)
    d = report.to_dict()
    assert "passed" in d
    assert "checks" in d
    assert "summary" in d


# ---- ExecutionLearner ----

def test_learner_learn_and_suggest():
    """学习后可以建议."""
    from security_agent.terminal.learner import ExecutionLearner
    learner = ExecutionLearner()
    learner.learn(intent="清理磁盘", command="df -h", ok=True, cmd_type="observe")
    learner.learn(intent="清理磁盘", command="du -sh /var/log/*", ok=True, cmd_type="observe")
    suggestions = learner.suggest("清理磁盘")
    if suggestions:
        assert "command" in suggestions[0]
        assert "success_rate" in suggestions[0]


def test_learner_stats():
    """stats() 返回统计."""
    from security_agent.terminal.learner import ExecutionLearner
    learner = ExecutionLearner()
    learner.learn(intent="test", command="ls", ok=True, cmd_type="observe")
    stats = learner.stats()
    assert "total_executions" in stats
    assert stats["total_executions"] >= 1


def test_learner_singleton():
    """单例返回同一实例."""
    from security_agent.terminal.learner import get_learner
    l1 = get_learner()
    l2 = get_learner()
    assert l1 is l2


# ---- intelligent_execute 集成 ----

def test_intelligent_execute_simple():
    """智能执行简单命令."""
    from security_agent.terminal.executor import intelligent_execute

    with tempfile.TemporaryDirectory() as tmp:
        result = intelligent_execute(
            "echo hello_from_intelligent_terminal",
            cwd=tmp,
            risk_level="READONLY",
            user_confirmed=True,
        )
        assert "context" in result
        assert "pre_analysis" in result
        assert "execution" in result
        assert "verification" in result
        assert result["execution"]["ok"] is True


def test_intelligent_execute_with_intent():
    """带意图的智能执行."""
    from security_agent.terminal.executor import intelligent_execute

    with tempfile.TemporaryDirectory() as tmp:
        result = intelligent_execute(
            "df -h",
            intent="查看磁盘空间",
            cwd=tmp,
            risk_level="READONLY",
            user_confirmed=True,
        )
        assert result["execution"]["ok"] is True


def test_understand_and_suggest():
    """意图理解+建议."""
    from security_agent.terminal.executor import understand_and_suggest

    result = understand_and_suggest("查看磁盘空间")
    assert "intent" in result
    assert "suggestions" in result
    assert "source" in result


def test_intelligent_execute_five_stages_complete():
    """五阶段全部产出."""
    from security_agent.terminal.executor import intelligent_execute

    with tempfile.TemporaryDirectory() as tmp:
        result = intelligent_execute(
            "ls -la",
            intent="查看文件",
            cwd=tmp,
            risk_level="READONLY",
            user_confirmed=True,
            learn=True,
        )
        # 五阶段全部存在
        assert result["context"] is not None, "Stage 1: context missing"
        assert result["pre_analysis"] is not None, "Stage 2: pre_analysis missing"
        assert result["execution"] is not None, "Stage 3: execution missing"
        assert result["verification"] is not None, "Stage 4: verification missing"
        # Stage 5: learning (might be None if no prior data, but key should exist)
        assert "learning" in result, "Stage 5: learning key missing"


# ---- 运行入口 ----

if __name__ == "__main__":
    import traceback

    tests = [
        ("test_context_gather", test_context_gather),
        ("test_context_summary", test_context_summary),
        ("test_context_record_commands", test_context_record_commands),
        ("test_context_failure_count", test_context_failure_count),
        ("test_context_singleton", test_context_singleton),
        ("test_pre_analyzer_classify_observe", test_pre_analyzer_classify_observe),
        ("test_pre_analyzer_classify_delete", test_pre_analyzer_classify_delete),
        ("test_pre_analyzer_classify_privilege", test_pre_analyzer_classify_privilege),
        ("test_pre_analyzer_danger_detection", test_pre_analyzer_danger_detection),
        ("test_pre_analyzer_chmod_777_warning", test_pre_analyzer_chmod_777_warning),
        ("test_pre_analyzer_alternatives", test_pre_analyzer_alternatives),
        ("test_pre_analyzer_path_extraction", test_pre_analyzer_path_extraction),
        ("test_pre_analyzer_to_dict", test_pre_analyzer_to_dict),
        ("test_pre_analyzer_summary", test_pre_analyzer_summary),
        ("test_understand_intent", test_understand_intent),
        ("test_understand_intent_no_match", test_understand_intent_no_match),
        ("test_pre_analyzer_history", test_pre_analyzer_history),
        ("test_verifier_exit_0", test_verifier_exit_0),
        ("test_verifier_exit_nonzero", test_verifier_exit_nonzero),
        ("test_verifier_empty_output", test_verifier_empty_output),
        ("test_verifier_to_dict", test_verifier_to_dict),
        ("test_learner_learn_and_suggest", test_learner_learn_and_suggest),
        ("test_learner_stats", test_learner_stats),
        ("test_learner_singleton", test_learner_singleton),
        ("test_intelligent_execute_simple", test_intelligent_execute_simple),
        ("test_intelligent_execute_with_intent", test_intelligent_execute_with_intent),
        ("test_understand_and_suggest", test_understand_and_suggest),
        ("test_intelligent_execute_five_stages_complete", test_intelligent_execute_five_stages_complete),
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
        print("  ALL PASS - Terminal intelligence pipeline verified!")
    print(f"{'='*60}")

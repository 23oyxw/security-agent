"""端到端验证 #4: 推理链路全链路追溯 — Trace ID + 思考/操作/安全检查记录.

测试覆盖:
  1. Trace 创建与生命周期
  2. Thought 记录 — 7 种思考类型
  3. Action 记录 — 工具调用 + tool_id + 参数
  4. SafetyCheck 记录 — 三层防御评分+决策路径
  5. KnowledgeReference RAG 引用
  6. ErrorRecord 异常记录
  7. Checkpoint 断点保存
  8. 完整报告 (summary/full_report/json)
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security_agent.audit.reasoning_trace import (
    TraceStatus,
    ThoughtType,
    ActionPhase,
    ReasoningTrace,
    CheckpointData,
)


# =============================================================================
# 测试用例
# =============================================================================


def test_01_trace_lifecycle():
    """T1: Trace 完整生命周期."""
    trace = ReasoningTrace(
        user_message="查看CPU使用率",
    )
    
    assert trace.status in (TraceStatus.CREATED,)
    assert trace.trace_id.startswith("trace-")
    assert len(trace.thoughts) == 0
    assert len(trace.actions) == 0
    
    # 推进到推理阶段
    trace.update_status(TraceStatus.REASONING)
    assert trace.status == TraceStatus.REASONING
    
    # 完成
    trace.update_status(TraceStatus.COMPLETED)
    assert trace.status == TraceStatus.COMPLETED
    
    summary = trace.to_summary()
    assert summary["status"] == "completed"
    
    print(f"  ✅ T1: 生命周期 created → reasoning → completed OK")


def test_02_record_thoughts():
    """T2: 记录多种思考类型."""
    trace = ReasoningTrace(user_message="诊断系统问题")
    
    types_to_test = [
        (ThoughtType.OBSERVATION, "CPU使用率92%，异常偏高"),
        (ThoughtType.HYPOTHESIS, "假设：某个进程占用过高"),
        (ThoughtType.REASONING, "对比历史数据，当前值偏离3σ"),
        (ThoughtType.PLANNING, "计划: 先查进程列表，再定位高占用者"),
        (ThoughtType.DECISION, "结论：nginx worker进程异常，建议重启"),
        (ThoughtType.REFLECTION, "反思：应先确认是否为正常业务高峰"),
        (ThoughtType.UNCERTAINTY, "不确定：日志时间戳可能有时区偏移问题"),
    ]
    
    for thought_type, content in types_to_test:
        trace.record_thought(thought_type=thought_type, content=content)
    
    assert len(trace.thoughts) == len(types_to_test)
    
    for i, (expected_type, _) in enumerate(types_to_test):
        assert trace.thoughts[i].thought_type == expected_type.value
    
    print(f"  ✅ T2: {len(types_to_test)} 种思考类型全部记录")


def test_03_record_actions():
    """T3: 记录工具操作（含tool_id/参数/结果）."""
    trace = ReasoningTrace(user_message="查询内存")
    
    actions_data = [
        ("query_metrics", "mcp.metric.cpu.001", {"metric": "cpu"}, '{"used": "45%"}'),
        ("log_search", "mcp.log.search.001", {"keyword": "error"}, '{"hits": 3}'),
        ("config_read", "mcp.config.nginx.001", {"path": "/etc/nginx.conf"}, '["workers 4"]'),
    ]
    
    for tool_name, tool_id, args, result in actions_data:
        trace.record_action(
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=args,
            phase=ActionPhase.EXECUTING,
            result_summary=result[:50],
            execution_time_ms=12.5,
        )
    
    assert len(trace.actions) == 3
    assert trace.actions[0].tool_id == "mcp.metric.cpu.001"
    assert trace.actions[1].arguments == {"keyword": "error"}
    
    print(f"  ✅ T3: {len(actions_data)} 个操作记录完整（含tool_id+参数+结果）")


def test_04_safety_checks():
    """T4: 三层安全防御校验记录."""
    trace = ReasoningTrace(user_message="执行修复命令")
    
    # 三层防御综合校验
    trace.record_safety_check(
        target="command_exec:systemctl restart nginx",
        target_type="terminal",
        layer_scores={
            "L1_static_risk": 35,
            "L2_intent_audit": 10,
            "L3_restricted_exec": 20,
        },
        overall_verdict="ALLOWED",
        overall_score=65.5,
        decision_path=["L1:MODERATE(35)", "L2:PASS(10)", "L3:SAFE(20)", "FINAL:ALLOWED"],
    )
    
    checks = trace.safety_checks
    assert len(checks) == 1
    assert checks[0].overall_verdict == "ALLOWED"
    assert checks[0].overall_score == 65.5
    # layer_scores 存储原始传入的字典
    assert "L1_static_risk" in str(checks[0].layer_scores)
    
    print(f"  ✅ T4: 三层安全校验记录 (verdict={checks[0].overall_verdict}, score={checks[0].overall_score})")


def test_05_knowledge_references():
    """T5: RAG 知识引用记录."""
    trace = ReasoningTrace(user_message="排查nginx错误")
    
    trace.record_knowledge_ref(
        query="nginx 502 error troubleshooting",
        matched_docs=[
            {"id": "doc-001", "title": "Nginx 502 排查指南"},
            {"id": "doc-042", "title": "Web服务故障处理流程"},
        ],
        relevance_scores=[0.92, 0.87],
    )
    
    krefs = trace.knowledge_refs
    assert len(krefs) == 1
    assert krefs[0].query == "nginx 502 error troubleshooting"
    assert len(krefs[0].matched_docs) == 2
    assert krefs[0].relevance_scores[0] == 0.92
    
    print(f"  ✅ T5: RAG知识引用已记录 ({len(krefs[0].matched_docs)}篇文档)")


def test_06_error_records():
    """T6: 异常/错误记录."""
    trace = ReasoningTrace(user_message="执行任务")
    
    trace.record_thought(ThoughtType.OBSERVATION, "开始分析")
    
    trace.record_error(
        error_type="ConnectionTimeout",
        error_message="连接数据库超时 (30s)",
        recovered=True,
        recovery_action="切换到本地缓存数据",
    )
    
    errors = trace.errors
    assert len(errors) == 1
    assert errors[0].recovered is True
    assert errors[0].error_type == "ConnectionTimeout"
    
    print(f"  ✅ T6: 错误记录 + 可恢复标记 OK")


def test_07_checkpoint_save():
    """T7: 断点保存供续跑."""
    trace = ReasoningTrace(
        user_message="自主修复磁盘问题",
        session_id="sess-checkpoint-007",
    )
    
    trace.record_thought(ThoughtType.OBSERVATION, "开始分析")
    trace.record_action(
        tool_name="check_disk_usage", tool_id="mcp.disk.001",
        arguments={}, result_summary='{"used": "95%"}',
    )
    trace.record_thought(ThoughtType.HYPOTHESIS, "日志文件过大导致磁盘满")
    
    checkpoint = trace.save_checkpoint(pending_actions=[
        {"step": "clean_old_logs", "args": {"days": 30}},
        {"step": "verify_disk", "args": {}},
    ])
    
    assert isinstance(checkpoint, CheckpointData)
    assert checkpoint.checkpoint_id.startswith("cp-")
    assert checkpoint.completed_steps >= 1
    assert len(checkpoint.pending_actions) == 2
    
    print(f"  ✅ T7: 断点保存成功 ({checkpoint.completed_steps}步, {len(checkpoint.pending_actions)}个待办)")


def test_08_full_report():
    """T8: 完整报告生成（summary + full_report + json）."""
    trace = ReasoningTrace(
        user_message="全面检查系统健康状态",
        session_id="sess-report",
    )
    
    trace.record_thought(ThoughtType.OBSERVATION, "收到全面检查请求")
    trace.record_action(
        tool_name="query_metrics", tool_id="mcp.metrics.001",
        arguments={"metric": "all"}, result_summary='{"cpu": 45}',
        execution_time_ms=12,
    )
    trace.record_safety_check(
        target="query_metrics:all", target_type="api_call",
        layer_scores={"L1": 5, "L2": 5, "L3": 5},
        overall_verdict="ALLOWED", overall_score=93.0,
        decision_path=["ALL_PASS"],
    )
    trace.record_knowledge_ref(
        query="系统健康检查",
        matched_docs=[{"id": "hc-001", "title": "健康检查标准"}],
        relevance_scores=[0.9],
    )
    
    summary = trace.to_summary()
    assert "trace_id" in summary and "total_thoughts" in summary
    assert summary["total_thoughts"] >= 1
    
    full = trace.to_full_report()
    assert "thoughts" in full and "actions" in full
    assert "safety_checks" in full and "knowledge_refs" in full
    
    json_str = trace.to_json()
    data = json.loads(json_str)
    assert data["user_message"] == "全面检查系统健康状态"
    
    print(f"  ✅ T8: Summary({len(summary)}键) + FullReport({len(full)}键) + JSON({len(json_str)}B)")


# =============================================================================
# 主入口
# =============================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("  三层核心功能验证 #4: 推理链路全链路追溯 (Trace ID)")
    print("=" * 65)

    tests = [
        ("T1 生命周期",              test_01_trace_lifecycle),
        ("T2 思考记录(7种类型)",     test_02_record_thoughts),
        ("T3 操作记录(tool_id+参数)", test_03_record_actions),
        ("T4 三层安全校验",          test_04_safety_checks),
        ("T5 RAG知识引用",           test_05_knowledge_references),
        ("T6 错误/异常记录",         test_06_error_records),
        ("T7 断点保存",              test_07_checkpoint_save),
        ("T8 完整报告生成",          test_08_full_report),
    ]

    passed = failed = 0
    errors = []

    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  ❌ {name}: {e}")

    print("-" * 65)
    total = passed + failed
    pct = (passed / total * 100) if total else 0
    print(f"  结果: {passed}/{total} 通过 ({pct:.0f}%)")

    if errors:
        print("\n  失败详情:")
        for name, err in errors:
            print(f"    • {name}: {err[:120]}")
    else:
        print("  🎉 所有测试通过！推理链路追溯端到端跑通 ✓")

    sys.exit(0 if failed == 0 else 1)

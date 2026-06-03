"""自主运维 goal 解析与编排参数."""

from security_agent.agent.orchestrator import (
    build_plan,
    build_tool_args,
    detect_intent,
    resolve_autonomous_goal,
)


def test_detect_autonomous_intent():
    assert detect_intent("执行自主运维任务") == "autonomous"


def test_resolve_default_goal_for_sidebar_phrase():
    g = resolve_autonomous_goal("执行自主运维任务")
    assert "全量安全巡检" in g
    assert "端口" in g or "高危" in g


def test_resolve_explicit_subgoal():
    g = resolve_autonomous_goal("自主运维：高危进程排查")
    assert "高危进程" in g


def test_build_tool_args_includes_goal():
    args = build_tool_args("run_autonomous_mission", "执行自主运维任务")
    assert args["goal"]
    assert len(args["goal"]) > 10


def test_build_plan_has_tool_args_for_autonomous():
    plan = build_plan("执行自主运维任务")
    assert plan["intent"] == "autonomous"
    assert plan["tool_chain"] == ["run_autonomous_mission"]
    assert "run_autonomous_mission" in plan.get("tool_args", {})
    assert plan["tool_args"]["run_autonomous_mission"]["goal"]

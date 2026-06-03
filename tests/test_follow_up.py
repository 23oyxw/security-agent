from security_agent.agent.follow_up import is_short_affirmative, resolve_follow_up
from security_agent.agent.orchestrator import build_plan, detect_intent


def test_detect_process_check_intent():
    assert detect_intent("检查异常进程") == "processes"


def test_affirmative_vnc_follow_up():
    history = [
        {
            "role": "assistant",
            "content": "端口 5900 vino-server PID 4911。方案一：killall vino-server",
        }
    ]
    fu = resolve_follow_up("需要", history)
    assert fu is not None
    assert fu["skill_flow"] == "secure_exec"
    plan = build_plan("需要", history)
    assert plan["skill_flow"] == "secure_exec"
    assert "killall" in plan.get("user_message_resolved", "")


def test_process_plan_has_two_tools():
    plan = build_plan("检查异常进程")
    assert plan["intent"] == "processes"
    assert "list_processes" in plan["tool_chain"]
    assert "check_exposed_ports" in plan["tool_chain"]

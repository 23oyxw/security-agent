"""L2 回复格式化."""

from security_agent.agent.skill_flow_format import format_secure_exec_reply


def test_secure_exec_readable_not_json():
    result = {
        "ok": True,
        "display_name": "安全命令执行",
        "trace_id": "abc123",
        "command": "ls -la /tmp",
        "defense": {
            "overall_verdict": "allow",
            "overall_score": 93.25,
            "message": "所有安全检查通过",
            "layers": [
                {"layer": "static_risk", "verdict": "pass", "score": 95, "detail": "只读观测"},
            ],
        },
        "execution": {
            "allowed": True,
            "execution_result": {
                "ok": True,
                "exit_code": 0,
                "stdout": "total 100\ndrwxrwxrwt tmp",
                "stderr": "",
            },
        },
    }
    text = format_secure_exec_reply(result)
    assert "defense_result" not in text
    assert "ls -la /tmp" in text
    assert "total 100" in text
    assert "L1 静态风险" in text
    assert "三层防御" in text

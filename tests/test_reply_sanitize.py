from security_agent.agent.reply_sanitize import is_markup_heavy, sanitize_assistant_reply


def test_strip_dsml():
    raw = "<｜｜DSML｜｜tool_calls>\n<｜｜DSML｜｜invoke name=\"search_security_knowledge\">"
    clean = sanitize_assistant_reply(raw)
    assert "DSML" not in clean
    assert is_markup_heavy(raw)

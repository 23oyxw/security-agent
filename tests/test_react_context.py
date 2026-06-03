"""ReAct 上下文治理单元测试."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from security_agent.agent.react_context import (
    apply_history_budget,
    build_react_user_message,
    truncate_observation,
)
from security_agent import config


def test_truncate_observation_short_unchanged():
    text = "ok"
    assert truncate_observation(text) == text


def test_truncate_observation_long_has_marker():
    limit = 100
    text = "a" * 500
    out = truncate_observation(text, max_chars=limit)
    assert len(out) < len(text)
    assert "观测已截断" in out
    assert out.startswith("a")
    assert out.endswith("a")


def test_build_react_user_message_caps_and_role():
    msg = build_react_user_message(
        "用户问题",
        "G" * (config.REACT_GROUNDING_MAX_CHARS + 100),
        "S" * (config.REACT_PERCEPTION_MAX_CHARS + 100),
        "P" * (config.REACT_PLANNER_NOTE_MAX_CHARS + 100),
    )
    assert msg["role"] == "user"
    assert "知识库 grounding 已截断" in msg["content"]
    assert "环境感知已截断" in msg["content"]
    assert "用户问题" in msg["content"]
    assert len(msg["content"]) < (
        config.REACT_GROUNDING_MAX_CHARS
        + config.REACT_PERCEPTION_MAX_CHARS
        + config.REACT_PLANNER_NOTE_MAX_CHARS
        + 200
    )


def test_apply_history_budget_truncates_tool_role():
    long_tool = "x" * 5000
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "tool", "tool_call_id": "1", "name": "t", "content": long_tool},
    ]
    tm = MagicMock()
    tm.should_compress.return_value = False
    out = apply_history_budget(messages, tm, max_round_msgs=2)
    tool_msg = [m for m in out if m.get("role") == "tool"][0]
    assert len(tool_msg["content"]) < len(long_tool)
    assert "观测已截断" in tool_msg["content"]


def test_apply_history_budget_compress_when_needed():
    messages = [{"role": "user", "content": "a"}]
    tm = MagicMock()
    tm.should_compress.return_value = True
    tm.compress_messages.return_value = [{"role": "user", "content": "compressed"}]
    out = apply_history_budget(messages, tm)
    tm.compress_messages.assert_called_once()
    assert out[0]["content"] == "compressed"


if __name__ == "__main__":
    test_truncate_observation_short_unchanged()
    test_truncate_observation_long_has_marker()
    test_build_react_user_message_caps_and_role()
    test_apply_history_budget_truncates_tool_role()
    test_apply_history_budget_compress_when_needed()
    print("test_react_context: all passed")

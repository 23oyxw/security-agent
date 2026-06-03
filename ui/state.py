"""Streamlit session state helpers."""

from __future__ import annotations

import streamlit as st

from security_agent import config
from security_agent.agent.brain import AgentBrain, LocalToolExecutor
from security_agent.agent.cost import CostTracker, get_global_tracker
from security_agent.monitor import get_monitor_service
from security_agent.scanner import engine as scanner


def init() -> None:
    defaults = {
        "last_scan": None,
        "chat_messages": [],
        "brain": None,
        "proc_rows": None,
        "_nav": "总览",
        "_model_preset": config.DEFAULT_MODEL_PRESET,
        "_chat_session_id": "default",
        "tool_user_confirmed": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # 保证监控单例在 session 内可复用
    st.session_state.setdefault("_monitor_bound", True)
    get_monitor_service()


def get_brain() -> AgentBrain | None:
    if not config.llm_configured():
        return None

    preset_name = st.session_state.get("_model_preset", config.DEFAULT_MODEL_PRESET)
    preset = config.MODEL_PRESETS.get(preset_name, config.MODEL_PRESETS[config.DEFAULT_MODEL_PRESET])

    # 如果预设的 API Key 为空，回退到默认 LLM
    if not preset.get("api_key"):
        preset = config.MODEL_PRESETS[config.DEFAULT_MODEL_PRESET]

    confirmed = bool(st.session_state.get("tool_user_confirmed", False))
    session_id = st.session_state.get("_chat_session_id", "default")

    brain = st.session_state.brain
    if brain is not None:
        current_model = getattr(brain, "model", None)
        if current_model != preset["model"].lower():
            st.session_state.brain = None
            brain = None

    if brain is None:
        try:
            st.session_state.brain = AgentBrain(
                api_key=preset["api_key"],
                base_url=preset["base_url"],
                model=preset["model"],
                session_id=session_id,
                user_confirmed=confirmed,
            )
        except (ValueError, Exception):
            return None
    else:
        brain.user_confirmed = confirmed
        if isinstance(brain.executor, LocalToolExecutor):
            brain.executor.user_confirmed = confirmed
    return st.session_state.brain


def get_active_model_info() -> dict[str, str]:
    """返回当前激活模型的简要信息."""
    preset_name = st.session_state.get("_model_preset", config.DEFAULT_MODEL_PRESET)
    preset = config.MODEL_PRESETS.get(preset_name, config.MODEL_PRESETS[config.DEFAULT_MODEL_PRESET])
    return {
        "name": preset_name,
        "model": preset.get("model", ""),
        "base_url": preset.get("base_url", ""),
    }


def run_scan() -> dict:
    data = scanner.run_security_scan()
    st.session_state.last_scan = data
    return data


def get_cost_tracker() -> CostTracker:
    """获取会话级别的成本追踪器."""
    if "cost_tracker" not in st.session_state:
        st.session_state.cost_tracker = CostTracker()
    return st.session_state.cost_tracker


def reset_cost_tracker() -> None:
    """重置成本追踪器."""
    if "cost_tracker" in st.session_state:
        del st.session_state.cost_tracker


def get_session_cost_summary() -> dict:
    """获取当前会话的成本汇总."""
    tracker = get_cost_tracker()
    return tracker.get_summary()

"""快捷提问组件：侧栏与智能助手页共用。"""

from __future__ import annotations

import streamlit as st

CHAT_SHORTCUTS: tuple[str, ...] = (
    "扫描系统风险",
    "列出高危进程",
    "一键综合体检",
    "生成 HTML 报告",
    "启动监控",
)


def _enqueue_and_go(text: str) -> None:
    st.session_state._chat_queue = text
    st.session_state["_nav"] = "智能助手"
    st.rerun()


def render_sidebar_shortcuts(*, on_chat_page: bool) -> None:
    """侧栏：带边框的快捷提问块，点击跳转智能助手。"""
    with st.container(border=True):
        st.markdown(
            '<p class="chat-shortcuts-title">快捷提问</p>'
            '<p class="chat-shortcuts-hint">点击后跳转「智能助手」并发送</p>',
            unsafe_allow_html=True,
        )
        for ex in CHAT_SHORTCUTS:
            if st.button(ex, key=f"sb_ex_{ex}", use_container_width=True):
                _enqueue_and_go(ex)
        if on_chat_page and st.button("清空对话", key="sb_clear_chat", use_container_width=True):
            st.session_state.chat_messages = []
            if st.session_state.get("brain"):
                st.session_state.brain.reset()
            st.rerun()


def render_chat_page_shortcuts() -> None:
    """智能助手页：横向快捷按钮（当前页，不跳转）。"""
    with st.container(border=True):
        st.markdown(
            '<p class="chat-shortcuts-title">快捷提问</p>'
            '<p class="chat-shortcuts-hint">在本页直接发送</p>',
            unsafe_allow_html=True,
        )
        cols = st.columns(len(CHAT_SHORTCUTS))
        for col, label in zip(cols, CHAT_SHORTCUTS, strict=True):
            with col:
                if st.button(label, key=f"chat_ex_{label}", use_container_width=True):
                    st.session_state._chat_queue = label
                    st.rerun()

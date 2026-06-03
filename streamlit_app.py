#!/usr/bin/env python3
"""Streamlit 入口 — 安全运维 Agent 控制台."""

from __future__ import annotations

import streamlit as st

from security_agent import config
from ui import state
from ui.pages import PAGES, render_sidebar
from ui.layout import inject_global_scroll
from ui.theme import inject

config.ensure_data_dirs()

st.set_page_config(
    page_title="安全运维 Agent",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_global_alert_bar() -> None:
    """全局告警横幅 — 在任何页面顶部显示未读高危告警（不需切到监控页）."""
    try:
        from security_agent.notify.alerts import get_unread_count, read_recent_alerts
        unread = get_unread_count()
    except Exception:
        return

    if unread <= 0:
        return

    # 首次检测到新告警时自动 toast 通知
    last_seen = st.session_state.get("_last_alert_count", 0)
    if unread > last_seen:
        st.session_state["_last_alert_count"] = unread
        # 获取最新一条告警
        try:
            alerts = read_recent_alerts(1)
            if alerts:
                a = alerts[0]
                level = a.get("level", "")
                atype = a.get("type", "")
                msg = (a.get("message") or "")[:100]
                st.toast(f"🚨 [{level}] {atype}: {msg}", icon="🚨")
        except Exception:
            pass

    # 横幅（可关闭）
    if not st.session_state.get("_alert_bar_dismissed"):
        try:
            alerts = read_recent_alerts(3)
            latest = alerts[0] if alerts else {}
            level = latest.get("level", "")
            atype = latest.get("type", "")
            msg = (latest.get("message") or "")[:120]
            st.markdown(
                f'<div class="global-alert-bar">'
                f'<span class="alert-text">🚨 <b>{unread}</b> 条未读告警 · '
                f'最新: <b>[{level}] {atype}</b> — {msg}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            pass

        # 操作按钮：横向紧凑
        ac1, ac2, ac3 = st.columns([1, 1, 4])
        with ac1:
            if st.button("查看详情", key="global_alert_view", use_container_width=True):
                st.session_state["_nav"] = "系统监控"
                st.session_state["_alert_bar_dismissed"] = False
                st.rerun()
        with ac2:
            if st.button("标记已读", key="global_alert_dismiss", use_container_width=True):
                from security_agent.notify.alerts import mark_alerts_read
                mark_alerts_read()
                st.session_state["_last_alert_count"] = 0
                st.session_state["_alert_bar_dismissed"] = True
                st.rerun()


def main() -> None:
    state.init()
    inject_global_scroll()
    inject()

    # 全局告警横幅（所有页面顶部）
    _render_global_alert_bar()

    with st.sidebar:
        page = render_sidebar()
    # 侧栏快捷提问：若带了队列且当前页不是助手，仍切到助手页
    if st.session_state.get("_chat_queue") and page != "智能助手":
        page = "智能助手"
        st.session_state["_nav"] = "智能助手"
    PAGES[page]()


if __name__ == "__main__":
    main()

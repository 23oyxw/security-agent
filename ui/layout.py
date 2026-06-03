"""页面布局 — 整页滚动与局部滚动容器."""

from __future__ import annotations

import streamlit as st

# 全局：系统浏览器整页滚动（兼容 Chrome / 麒麟浏览器 / Cursor 预览差异）
GLOBAL_SCROLL_CSS = """
<style>
    html, body {
        overflow-y: auto !important;
        overflow-x: hidden !important;
        height: auto !important;
    }
    [data-testid="stApp"],
    .stApp {
        overflow-y: auto !important;
        overflow-x: hidden !important;
        height: auto !important;
        min-height: 100vh;
    }
    [data-testid="stAppViewContainer"] {
        overflow-y: auto !important;
        overflow-x: hidden !important;
        height: auto !important;
        min-height: 100vh;
    }
    [data-testid="stAppViewContainer"] > section.main,
    section[data-testid="stMain"],
    section.main {
        overflow: visible !important;
        height: auto !important;
        min-height: 0 !important;
    }
    section.main > div.block-container,
    section[data-testid="stMain"] > div.block-container {
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }
    [data-testid="stSidebar"] > div {
        overflow-y: auto !important;
    }
    .sec-page-scroll {
        max-height: min(70vh, 720px);
        overflow-y: auto !important;
        overflow-x: hidden !important;
        padding-right: 0.35rem;
        margin-bottom: 0.5rem;
    }
    div[data-testid="stPlotlyChart"] {
        margin-bottom: 1rem !important;
    }
    div[data-testid="stPlotlyChart"] iframe {
        max-width: 100% !important;
    }
</style>
"""

CHAT_INPUT_CSS = """
<style>
    section.main > div.block-container,
    section[data-testid="stMain"] > div.block-container {
        padding-bottom: 8rem !important;
    }
    [data-testid="stBottomBlock"] {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        z-index: 999 !important;
        background: #0e1117 !important;
        border-top: 1px solid #2d3f54 !important;
        padding: 0.5rem 1rem 0.75rem 1rem !important;
    }
    div[data-testid="stChatInput"],
    div[data-testid="stChatInput"] > div {
        max-width: 100% !important;
    }
    @media (min-width: 768px) {
        [data-testid="stSidebar"][aria-expanded="true"] ~ [data-testid="stAppViewContainer"] [data-testid="stBottomBlock"] {
            margin-left: 21rem !important;
            width: calc(100% - 21rem) !important;
        }
    }
    .sec-chat-scroll {
        max-height: min(60vh, 560px);
        overflow-y: auto !important;
        overflow-x: hidden !important;
        padding-right: 0.25rem;
    }
</style>
"""


def inject_global_scroll() -> None:
    st.markdown(GLOBAL_SCROLL_CSS, unsafe_allow_html=True)


def inject_scroll_page() -> None:
    inject_global_scroll()


def inject_chat_layout() -> None:
    st.markdown(GLOBAL_SCROLL_CSS + CHAT_INPUT_CSS, unsafe_allow_html=True)


def scroll_container(height: int = 420):
    return st.container(height=height)


def inject_fixed_input_layout() -> None:
    inject_chat_layout()

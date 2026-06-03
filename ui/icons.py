"""页面标题与按钮文案 — 仅用 CSS 色块图标，避免 emoji 乱码."""

from __future__ import annotations

import streamlit as st

# icon 键 → theme.css 中 .sec-icon-{key}
PAGE_ICONS = {
    "overview": "OV",
    "autonomous": "AU",
    "scan": "SC",
    "process": "PR",
    "monitor": "MO",
    "demo": "DM",
    "chat": "AI",
    "report": "RP",
    "audit": "AU2",
    "brand": "SA",
}


def page_heading(title: str, icon_key: str) -> None:
    key = icon_key if icon_key in PAGE_ICONS else "overview"
    st.markdown(
        f'<h3 class="sec-page-title">'
        f'<span class="sec-icon sec-icon-{key}" aria-hidden="true"></span>'
        f"<span>{title}</span></h3>",
        unsafe_allow_html=True,
    )


def brand_header(title: str = "安全运维 Agent") -> None:
    st.markdown(
        f'<p class="main-header">'
        f'<span class="sec-icon sec-icon-brand" aria-hidden="true"></span>'
        f"<span>{title}</span></p>",
        unsafe_allow_html=True,
    )

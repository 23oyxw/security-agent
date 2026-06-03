"""知识库页面 — 浏览安全运维应急预案与 MCP 知识条目."""

from __future__ import annotations

import streamlit as st

from security_agent.knowledge.playbooks import PLAYBOOKS, PLAYBOOK_BY_ID


# 严重度排序权重
_SEV_ORDER = {"严重": 0, "高": 1, "中": 2, "低": 3, "信息": 4}


def page_knowledge() -> None:
    """知识库浏览页."""
    st.title("📚 安全知识库")
    st.caption("应急预案（Playbook）· 覆盖误删防护、窃密检测、端口暴露、权限管控等场景")

    total = len(PLAYBOOKS)
    c1, c2, c3 = st.columns(3)
    c1.metric("预案总数", total)
    c2.metric("严重/高", sum(1 for p in PLAYBOOKS if p.severity in ("严重", "高")))
    c3.metric("需 Root", sum(1 for p in PLAYBOOKS if p.requires_root_confirm))

    st.divider()

    # 筛选
    f1, f2 = st.columns(2)
    with f1:
        severities = ["全部"] + sorted(
            {p.severity for p in PLAYBOOKS}, key=lambda s: _SEV_ORDER.get(s, 99)
        )
        sev_filter = st.selectbox("按严重度筛选", severities, key="kb_sev")
    with f2:
        all_tags = sorted({t for p in PLAYBOOKS for t in p.threat_tags})
        tag_filter = st.selectbox("按标签筛选", ["全部"] + all_tags, key="kb_tag")

    # 搜索
    keyword = st.text_input("🔍 关键词搜索（匹配标题/ID/关键词）", "", key="kb_search")

    # 过滤
    filtered = list(PLAYBOOKS)
    if sev_filter != "全部":
        filtered = [p for p in filtered if p.severity == sev_filter]
    if tag_filter != "全部":
        filtered = [p for p in filtered if tag_filter in p.threat_tags]
    if keyword.strip():
        kw = keyword.strip().lower()
        filtered = [
            p for p in filtered
            if kw in p.id.lower()
            or kw in p.title.lower()
            or any(kw in k.lower() for k in p.keywords)
        ]

    st.caption(f"显示 {len(filtered)}/{total} 条预案")

    if not filtered:
        st.info("未找到匹配的预案")
        return

    # 按严重度排序展示
    filtered.sort(key=lambda p: _SEV_ORDER.get(p.severity, 99))

    for pb in filtered:
        sev_icon = {"严重": "🔴", "高": "🟠", "中": "🟡", "低": "🟢", "信息": "🔵"}.get(
            pb.severity, "⚪"
        )
        root_badge = " 🔒需Root" if pb.requires_root_confirm else ""

        with st.expander(f"{sev_icon} **{pb.id}** — {pb.title}{root_badge}", expanded=False):
            st.markdown(f"**严重度:** {pb.severity} {root_badge}")
            st.markdown(f"**标签:** {', '.join(pb.threat_tags)}")
            st.markdown(f"**关键词:** {', '.join(pb.keywords)}")
            st.divider()
            st.markdown("**预案内容:**")
            st.info(pb.body)

            if pb.do_not:
                st.markdown("**⛔ 禁止事项:**")
                for dn in pb.do_not:
                    st.markdown(f"- ❌ {dn}")

            if pb.suggested_actions:
                st.markdown("**✅ 建议动作:**")
                for sa in pb.suggested_actions:
                    st.markdown(f"- ✔ {sa}")
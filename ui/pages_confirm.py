"""确认对话框页面 — 处理用户确认请求（可独立运行，也可嵌入主框架）."""

from __future__ import annotations

import streamlit as st

from security_agent.confirm import get_confirmation_manager, ConfirmationStatus


def show_confirmation_page():
    """显示确认对话框页面"""
    st.title("🔒 安全操作确认")
    
    # 获取确认管理器
    manager = get_confirmation_manager()
    
    # 显示待处理的确认请求
    st.subheader("📋 待处理确认请求")
    
    pending_requests = manager.list_pending_requests()
    
    if not pending_requests:
        st.info("✅ 当前没有待处理的确认请求")
        return
    
    # 为每个请求显示确认卡片
    for request in pending_requests:
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"### 🔐 操作确认: {request.request_id}")
                st.markdown(f"**用户消息**: {request.user_message}")
                st.markdown(f"**操作描述**: {request.action_description}")
                st.markdown(f"**风险等级**: :red[{request.risk_level}]")
                st.markdown(f"**请求时间**: {request.requested_at}")
                
                # 显示元数据
                if request.metadata:
                    with st.expander("📊 详细信息"):
                        st.json(request.metadata)
            
            with col2:
                st.markdown("### 操作")
                
                # 批准按钮
                if st.button("✅ 批准", key=f"approve_{request.request_id}"):
                    reason = st.text_input("批准原因", key=f"reason_{request.request_id}")
                    if manager.approve_request(request.request_id, "user", reason):
                        st.success("✅ 已批准")
                        st.rerun()
                
                # 拒绝按钮
                if st.button("❌ 拒绝", key=f"reject_{request.request_id}"):
                    reason = st.text_input("拒绝原因", key=f"reject_reason_{request.request_id}")
                    if manager.reject_request(request.request_id, "user", reason):
                        st.error("❌ 已拒绝")
                        st.rerun()
            
            st.divider()


def show_confirmation_history():
    """显示确认历史"""
    st.subheader("📜 确认历史")
    
    manager = get_confirmation_manager()
    
    # 获取统计信息
    stats = manager.get_stats()
    
    # 显示统计
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("总请求数", stats.get("total_requests", 0))
    
    with col2:
        st.metric("待处理", stats.get("pending_count", 0))
    
    with col3:
        status_stats = stats.get("status_stats", {})
        approved = status_stats.get("approved", 0)
        st.metric("已批准", approved)
    
    # 显示状态分布
    if status_stats:
        st.subheader("状态分布")
        st.bar_chart(status_stats)


def page_confirm() -> None:
    """供主框架 PAGES 字典调用的入口（含子标签页切换）."""
    st.title("🔒 安全操作确认")

    tab_pending, tab_history = st.tabs(["📋 待处理", "📜 确认历史"])
    with tab_pending:
        show_confirmation_page()
    with tab_history:
        show_confirmation_history()


# ---------------------------------------------------------------------------
# 独立运行入口（streamlit run ui/pages_confirm.py）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    st.set_page_config(page_title="安全操作确认", page_icon="🔒", layout="wide")
    page_confirm()

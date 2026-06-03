"""UI theme — 纯 CSS 图标与状态点，不依赖 emoji 字体."""

import streamlit as st

CUSTOM_CSS = """
<style>
    .main-header {
        font-size: 1.75rem; font-weight: 700; color: #64B5F6;
        margin-bottom: 0.25rem; display: flex; align-items: center; gap: 0.5rem;
    }
    .sub-header { color: #90A4AE; font-size: 0.95rem; margin-bottom: 1rem; }
    .sec-page-title {
        font-size: 1.35rem; font-weight: 600; color: #E8EEF4;
        display: flex; align-items: center; gap: 0.5rem; margin: 0 0 0.75rem 0;
    }
    .sec-icon {
        display: inline-flex; align-items: center; justify-content: center;
        min-width: 2rem; height: 2rem; border-radius: 8px;
        font-size: 0.65rem; font-weight: 800; letter-spacing: -0.02em;
        flex-shrink: 0; border: 1px solid rgba(255,255,255,0.12);
    }
    .sec-icon-brand { background: linear-gradient(135deg, #1565C0, #0D47A1); color: #fff; }
    .sec-icon-brand::after { content: "SA"; }
    .sec-icon-overview { background: #1565C0; color: #fff; }
    .sec-icon-overview::after { content: "OV"; }
    .sec-icon-autonomous { background: #6A1B9A; color: #fff; }
    .sec-icon-autonomous::after { content: "AU"; }
    .sec-icon-scan { background: #00838F; color: #fff; }
    .sec-icon-scan::after { content: "SC"; }
    .sec-icon-process { background: #455A64; color: #fff; }
    .sec-icon-process::after { content: "PR"; }
    .sec-icon-monitor { background: #E65100; color: #fff; }
    .sec-icon-monitor::after { content: "MO"; }
    .sec-icon-demo { background: #AD1457; color: #fff; }
    .sec-icon-demo::after { content: "DM"; }
    .sec-icon-chat { background: #2E7D32; color: #fff; }
    .sec-icon-chat::after { content: "AI"; }
    .sec-icon-report { background: #5D4037; color: #fff; }
    .sec-icon-report::after { content: "RP"; }
    .sec-icon-audit { background: #37474F; color: #fff; }
    .sec-icon-audit::after { content: "LG"; }
    .status-dot {
        display: inline-block; width: 0.55rem; height: 0.55rem;
        border-radius: 50%; margin-right: 0.35rem; vertical-align: middle;
    }
    .status-dot-ok { background: #66bb6a; box-shadow: 0 0 6px rgba(102,187,106,0.6); }
    .status-dot-warn { background: #ffa726; }
    .status-dot-idle { background: #78909c; }
    .status-dot-bad { background: #ef5350; box-shadow: 0 0 6px rgba(239,83,80,0.5); }
    .status-ok, .status-warn, .status-bad, .status-idle { font-weight: 600; }
    .status-ok { color: #66bb6a; }
    .status-warn { color: #ffa726; }
    .status-bad { color: #ef5350; }
    .status-idle { color: #90a4ae; }
    .alert-banner {
        background: linear-gradient(90deg, #3e2723 0%, #1a2332 100%);
        border: 1px solid #ef5350; border-radius: 8px;
        padding: 0.6rem 0.9rem; margin-bottom: 0.75rem; color: #ffccbc;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1A2332 0%, #243447 100%);
        padding: 12px 16px; border-radius: 10px; border: 1px solid #2d3f54;
    }
    .monitor-metric-label { color: #90a4ae; font-size: 0.85rem; margin-bottom: 0.15rem; }
    .level-pill {
        display: inline-block; padding: 0.1rem 0.45rem; border-radius: 4px;
        font-size: 0.75rem; font-weight: 700;
    }
    .level-critical { background: #4a1515; color: #ff8a80; border: 1px solid #ef5350; }
    .level-high { background: #4a3010; color: #ffcc80; border: 1px solid #ffa726; }
    .level-mid { background: #2a3540; color: #90caf9; border: 1px solid #5c6bc0; }
    .level-info { background: #263238; color: #b0bec5; border: 1px solid #546e7a; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 8px; }
    .chat-shortcuts-title {
        margin: 0 0 0.15rem 0; font-size: 0.95rem; font-weight: 600; color: #e3f2fd;
    }
    .chat-shortcuts-hint {
        margin: 0 0 0.5rem 0; font-size: 0.75rem; color: #90a4ae;
    }
    /* 侧栏导航：紧凑分组 */
    .sidebar-nav-group {
        display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 0.5rem;
    }
    .sidebar-nav-btn {
        flex: 1 1 calc(50% - 4px); min-width: 0; padding: 6px 8px;
        border-radius: 6px; border: 1px solid #2d3f54; background: #1a2332;
        color: #b0bec5; font-size: 0.82rem; cursor: pointer; text-align: center;
        transition: all 0.15s ease;
    }
    .sidebar-nav-btn:hover { background: #243447; color: #e3f2fd; border-color: #42a5f5; }
    .sidebar-nav-btn.active { background: #1565c0; color: #fff; border-color: #42a5f5; font-weight: 600; }
    /* 告警角标 */
    .alert-badge {
        display: inline-flex; align-items: center; justify-content: center;
        min-width: 20px; height: 20px; padding: 0 6px;
        border-radius: 10px; background: #ef5350; color: #fff;
        font-size: 0.7rem; font-weight: 700; margin-left: 6px;
        animation: badge-pulse 2s ease-in-out infinite;
    }
    @keyframes badge-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    /* 全局告警横幅（页面顶部） */
    .global-alert-bar {
        position: sticky; top: 0; z-index: 999;
        background: linear-gradient(90deg, #3e2723 0%, #1a2332 100%);
        border: 1px solid #ef5350; border-radius: 8px;
        padding: 0.5rem 0.9rem; margin-bottom: 0.5rem; color: #ffccbc;
        display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;
    }
    .global-alert-bar .alert-text { flex: 1; font-size: 0.85rem; }
    /* 告警详情卡片 */
    .alert-card {
        background: #1a2332; border-left: 3px solid #ef5350; border-radius: 0 8px 8px 0;
        padding: 0.6rem 0.8rem; margin-bottom: 0.4rem;
    }
    .alert-card.warn { border-left-color: #ffa726; }
    .alert-card .alert-level { font-weight: 700; font-size: 0.8rem; }
    .alert-card .alert-type { font-weight: 600; color: #e3f2fd; }
    .alert-card .alert-msg { color: #b0bec5; font-size: 0.85rem; margin-top: 0.2rem; }
    .alert-card .alert-time { color: #78909c; font-size: 0.75rem; }
    /* 按钮间距 */
    div[data-testid="stButton"] { margin-bottom: 0.3rem; }
    /* 快捷按钮紧凑 */
    .shortcut-chip {
        display: inline-block; padding: 4px 10px; margin: 2px;
        border-radius: 14px; border: 1px solid #2d3f54; background: #1a2332;
        color: #90caf9; font-size: 0.8rem; cursor: pointer; transition: all 0.15s;
    }
    .shortcut-chip:hover { background: #1565c0; color: #fff; border-color: #42a5f5; }
</style>
"""


def inject() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def _status_line(dot_class: str, text: str) -> str:
    return f'<span class="status-{dot_class.split("-")[-1] if "dot" not in dot_class else dot_class}">' \
           f'<span class="status-dot {dot_class}"></span>{text}</span>'


def api_status_html(ok: bool) -> str:
    if ok:
        return (
            '<span class="status-ok">'
            '<span class="status-dot status-dot-ok"></span>API 已连接</span>'
        )
    return (
        '<span class="status-warn">'
        '<span class="status-dot status-dot-warn"></span>'
        "API 未配置（编辑 .env 后 boot_start）</span>"
    )


def monitor_status_html(running: bool) -> str:
    if running:
        return (
            '<span class="status-ok">'
            '<span class="status-dot status-dot-ok"></span>监控运行中</span>'
        )
    return (
        '<span class="status-idle">'
        '<span class="status-dot status-dot-idle"></span>监控已停止</span>'
    )


def litellm_status_html(status: dict) -> str:
    """LiteLLM代理状态显示."""
    if not status.get("enabled"):
        return (
            '<span class="status-idle">'
            '<span class="status-dot status-dot-idle"></span>代理未启用</span>'
        )
    if status.get("healthy"):
        return (
            '<span class="status-ok">'
            '<span class="status-dot status-dot-ok"></span>代理运行中</span>'
        )
    if status.get("running"):
        return (
            '<span class="status-warn">'
            '<span class="status-dot status-dot-warn"></span>代理启动中</span>'
        )
    return (
        '<span class="status-warn">'
        '<span class="status-dot status-dot-warn"></span>代理异常</span>'
    )


def level_pill_html(level: str) -> str:
    lv = (level or "").strip()
    if lv == "严重":
        cls = "level-critical"
    elif lv == "高":
        cls = "level-high"
    elif lv in ("中", "低"):
        cls = "level-mid"
    else:
        cls = "level-info"
    return f'<span class="level-pill {cls}">{lv or "信息"}</span>'

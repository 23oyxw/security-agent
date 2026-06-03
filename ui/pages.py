"""Streamlit page renderers."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pandas as pd
import psutil
import streamlit as st

from datetime import timedelta

from security_agent import config
from security_agent import __version__ as APP_VERSION
from security_agent.agent.cost import estimate_cost, format_cost_for_display, format_token_usage
from security_agent.agent.policy import summarize_risks
from security_agent.agent.rules import AUTOMATION_LEVEL
from security_agent.audit.log import read_audit_tail
from security_agent.config import REPORTS_DIR
from security_agent.monitor import get_monitor_service
from security_agent.timeutil import TZ_LABEL, format_display, format_file_mtime, now_filename_ts
from security_agent.scanner import engine as scanner
from ui import state
from ui.layout import inject_chat_layout, inject_scroll_page, scroll_container
from ui.safe_display import safe_json_data, safe_markdown
from ui.icons import brand_header, page_heading
from ui import risk_viz
from ui.theme import api_status_html, monitor_status_html, litellm_status_html
from ui.chat_shortcuts import render_chat_page_shortcuts, render_sidebar_shortcuts
from security_agent.notify.alerts import get_unread_count, mark_alerts_read, read_recent_alerts


def _risks_df(risks: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "等级": r.get("level", ""),
                "类型": r.get("type", ""),
                "PID": r.get("pid", ""),
                "对象": r.get("name") or r.get("path", ""),
                "用户": r.get("username", ""),
                "说明": (r.get("message") or r.get("cmdline", ""))[:200],
            }
            for r in risks
        ]
    )


def render_sidebar() -> str:
    brand_header()
    st.markdown(
        f'<p class="sub-header">{config.platform_label()} · v{APP_VERSION}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(api_status_html(config.llm_configured()), unsafe_allow_html=True)

    # LiteLLM 代理状态（A2赛题统一路由）
    litellm_status = config.litellm_status()
    st.markdown(litellm_status_html(litellm_status), unsafe_allow_html=True)
    if litellm_status["enabled"] and not litellm_status["healthy"]:
        st.caption(f"💡 代理地址: {litellm_status['url']}")

    monitor = get_monitor_service()

    # ---- 告警角标（侧栏顶部） ----
    _render_sidebar_alert_badge()

    st.divider()

    # ---- 快捷操作：2 列网格 ----
    sc1, sc2 = st.columns(2)
    with sc1:
        if st.button("🔍 立即扫描", use_container_width=True, key="sb_scan"):
            with st.spinner("扫描中…"):
                state.run_scan()
            st.session_state._nav = "安全扫描"
            st.rerun()
    with sc2:
        if monitor.running:
            if st.button("⏹ 停止监控", use_container_width=True, key="sb_mon_stop"):
                msg = monitor.stop()
                st.session_state._monitor_flash = msg
                st.toast(msg)
                st.rerun()
        else:
            if st.button("▶ 启动监控", use_container_width=True, key="sb_mon_start"):
                msg = monitor.start()
                st.session_state._monitor_flash = msg
                st.toast(msg)
                st.rerun()

    st.markdown(monitor_status_html(monitor.running), unsafe_allow_html=True)

    st.divider()

    # ---- 导航：紧凑 2 列网格按钮（替代 radio，防粘连） ----
    pages = [
        ("总览", "📊"),
        ("自主运维", "🤖"),
        ("安全扫描", "🔍"),
        ("进程管理", "⚙"),
        ("系统监控", "📡"),
        ("风险演练", "🎯"),
        ("Skill 插件", "🧩"),
        ("Skill 流程", "⚙"),
        ("知识库", "📚"),
        ("安全确认", "🔒"),
        ("智能助手", "💬"),
        ("报告中心", "📋"),
        ("审计日志", "📝"),
    ]
    current = st.session_state.get("_nav", "总览")

    # 分两排渲染，每排 5 个（最后一排 4 个）
    page = current  # 默认不变
    for row_start in range(0, len(pages), 5):
        row = pages[row_start : row_start + 5]
        cols = st.columns(len(row))
        for col, (name, icon) in zip(cols, row):
            with col:
                is_active = name == current
                btn_type = "primary" if is_active else "secondary"
                if st.button(
                    f"{icon} {name}",
                    key=f"nav_{name}",
                    type=btn_type,
                    use_container_width=True,
                ):
                    page = name
                    st.session_state["_nav"] = page
                    st.rerun()

    st.session_state["_nav"] = page

    # ---- 模型切换（radio 点击选择，不可编辑） ----
    st.divider()
    model_names = list(config.MODEL_PRESETS.keys())
    current_preset = st.session_state.get("_model_preset", config.DEFAULT_MODEL_PRESET)
    preset_idx = model_names.index(current_preset) if current_preset in model_names else 0
    selected = st.radio("🧠 对话模型", model_names, index=preset_idx, key="_model_select", label_visibility="collapsed")
    if selected != current_preset:
        st.session_state["_model_preset"] = selected
        st.session_state.brain = None
        st.session_state.chat_messages = []
        st.rerun()

    model_info = state.get_active_model_info()
    st.caption(f"当前: `{model_info['model']}`")

    # Budget 模型状态
    budget_configured = bool(config.BUDGET_API_KEY and config.BUDGET_API_KEY not in ("your_key_here", "sk-your-key-here"))
    if budget_configured:
        st.caption(f"💰 Budget: `{config.BUDGET_MODEL}` ✓")
    else:
        st.caption("💰 Budget: 未配置")

    # 并行模式状态
    st.caption("⚡ 并行执行: 已启用（只读工具）")

    # Fallback 状态（应用层自动回退）
    st.divider()
    st.caption("🔄 自动回退 (Fallback)")

    # 获取当前模型的 fallback 配置
    brain = state.get_brain()
    if brain:
        fallback_stats = brain.get_fallback_stats()
        if fallback_stats["fallback_available"]:
            st.caption(f"✅ 已启用")
            st.caption(f"主模型: {fallback_stats['primary_model'][:20]}")
            st.caption(f"备用: {fallback_stats['fallback_model'][:20]}")
            if fallback_stats["fallback_used_count"] > 0:
                st.success(f"已触发 {fallback_stats['fallback_used_count']} 次自动回退")
            with st.expander("什么是 Fallback？", expanded=False):
                st.markdown("""
                **Fallback** = 主模型失败时自动切换到备用模型

                **场景示例：**
                - MiMo 超时/限流 → 自动切换到 DeepSeek
                - 用户无感知，对话继续

                **配置方式：**
                - 自动识别：MiMo → DeepSeek V3
                - 基于 .env 中的 BUDGET_API_KEY
                """)
        else:
            st.caption("⚠️ 未配置备用模型")
            st.caption("*配置 DeepSeek API Key 启用自动回退*")
    else:
        st.caption("*Agent 未初始化*")

    # 会话成本统计
    cost_summary = state.get_session_cost_summary()

    st.divider()
    st.caption("📊 本会话统计")

    if cost_summary["calls"] > 0:
        cost_str = format_cost_for_display(cost_summary['total_cost_cny'])
        st.caption(f"调用: {cost_summary['calls']} 次 | Token: {cost_summary['total_tokens']:,}")
        st.caption(f"💰 预估成本: {cost_str}")

        # 显示各模型使用情况
        if cost_summary.get("by_model"):
            with st.expander("各模型详情", expanded=False):
                for model, info in cost_summary["by_model"].items():
                    model_cost = format_cost_for_display(info['cost_cny'])
                    st.caption(f"• {model[:20]}: {info['calls']}次, {model_cost}")

        # 重置按钮
        if st.button("🔄 重置统计", key="reset_cost_stats", use_container_width=True):
            state.reset_cost_tracker()
            st.rerun()
    else:
        st.caption("调用: 0 次 | Token: 0")
        st.caption("💰 预估成本: ¥0")
        st.caption("*成本统计将在首次调用后显示*")

    st.divider()
    render_sidebar_shortcuts(on_chat_page=(page == "智能助手"))
    st.session_state["_debug_mode"] = st.checkbox("调试模式（显示编排详情）", value=False, key="debug_toggle")

    st.caption(f"自动化: {AUTOMATION_LEVEL['level']}")

    st.caption(f"http://127.0.0.1:8501 · 时间均为 {TZ_LABEL}")
    return page


def _render_sidebar_alert_badge() -> None:
    """侧栏告警角标：显示未读告警数，点击展开详情."""
    try:
        unread = get_unread_count()
    except Exception:
        unread = 0

    if unread > 0:
        st.markdown(
            f'<span class="status-bad">'
            f'<span class="status-dot status-dot-bad"></span>'
            f'告警 <span class="alert-badge">{unread}</span></span>',
            unsafe_allow_html=True,
        )
        with st.expander(f"查看 {unread} 条未读告警", expanded=False):
            alerts = read_recent_alerts(10)
            for a in alerts[:5]:
                level = a.get("level", "")
                atype = a.get("type", "")
                msg = (a.get("message") or "")[:80]
                cls = "alert-card" if level in ("严重", "高") else "alert-card warn"
                st.markdown(
                    f'<div class="{cls}">'
                    f'<span class="alert-level">{level}</span> '
                    f'<span class="alert-type">{atype}</span>'
                    f'<div class="alert-msg">{msg}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if st.button("标记已读", key="sb_mark_read", use_container_width=True):
                mark_alerts_read()
                st.rerun()


def page_overview() -> None:
    inject_scroll_page()
    page_heading("安全态势总览", "overview")
    monitor = get_monitor_service()
    scan = st.session_state.last_scan

    # 系统资源
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("CPU", f"{cpu}%")
    c2.metric("内存", f"{mem.percent}%")
    c3.metric("磁盘", f"{disk.percent}%")
    with c4:
        st.markdown('<p class="monitor-metric-label">监控</p>', unsafe_allow_html=True)
        st.markdown(monitor_status_html(monitor.running), unsafe_allow_html=True)
    c5.metric("风险", len(scan["risks"]) if scan else "—")
    c6.metric("API", "ON" if config.llm_configured() else "OFF")

    ev_recent = monitor.get_events(30)
    posture = risk_viz.posture_score(
        scan.get("risks") if scan else None,
        ev_recent,
    )
    st.progress(posture["score"] / 100.0, text=f"综合态势 {posture['score']}/100 · {posture['label']}")

    if st.button("运行自检", type="secondary"):
        with st.spinner("自检中…"):
            data = state.run_scan()
            procs = scanner.list_processes(20)
            events = monitor.get_events(5)
        st.success(
            f"扫描 {data['risk_count']} 项风险 · "
            f"进程样本 {len(procs)} · 监控事件 {len(events)}"
        )

    # 按钮可能更新了 last_scan，重新读取
    scan = st.session_state.last_scan

    left, right = st.columns(2)
    with left:
        st.subheader("风险分布")
        if scan and scan.get("risks"):
            counts = summarize_risks(scan["risks"])
            cdf = pd.DataFrame({"等级": list(counts.keys()), "数量": list(counts.values())})
            cdf = cdf[cdf["数量"] > 0]
            if not cdf.empty:
                st.bar_chart(cdf.set_index("等级"))
        else:
            st.info("暂无扫描数据")

    with right:
        st.subheader("监控事件")
        ev = monitor.get_events(10)
        st.dataframe(pd.DataFrame(ev) if ev else pd.DataFrame(), use_container_width=True)

    if scan and scan.get("risks"):
        st.subheader("风险 TOP10")
        st.dataframe(_risks_df(scan["risks"][:10]), use_container_width=True, hide_index=True)


def page_scan() -> None:
    inject_scroll_page()
    page_heading("安全扫描", "scan")
    if st.button("立即扫描", type="primary"):
        data = state.run_scan()
        st.success(f"发现 {data['risk_count']} 项风险")

    data = st.session_state.last_scan
    if not data:
        st.info("点击「立即扫描」开始")
        return

    risks = data.get("risks", [])
    st.caption(f"{format_display(data.get('scanned_at'))} · {data.get('platform')} · {TZ_LABEL}")
    m1, m2, m3 = st.columns(3)
    m1.metric("总计", len(risks))
    m2.metric("高危进程", sum(1 for r in risks if r.get("type") == "高危进程"))
    m3.metric("权限异常", sum(1 for r in risks if r.get("type") == "权限异常"))

    if not risks:
        st.success("未发现风险")
        return

    tab_table, tab_viz = st.tabs(["风险列表", "多维态势"])
    with tab_table:
        st.dataframe(_risks_df(risks), use_container_width=True, hide_index=True)
    with tab_viz:
        posture = risk_viz.posture_score(risks, None)
        v1, v2 = st.columns(2)
        v1.metric("态势评分", f"{posture['score']}/100")
        v2.metric("态势等级", posture["label"])
        pts = risk_viz.risks_to_cube_points(risks)
        for p in pts:
            p["source"] = "scan"
        fig_c = risk_viz.fig_cube_3d(pts, title="本次扫描三维分布")
        if fig_c:
            st.plotly_chart(fig_c, width="stretch", config=risk_viz.PLOTLY_STATIC_CONFIG)
        fig_b = risk_viz.fig_level_bars(posture.get("counts", {}))
        if fig_b:
            st.plotly_chart(fig_b, width="stretch", config=risk_viz.PLOTLY_STATIC_CONFIG)
    if st.button("生成 HTML 报告"):
        path = scanner.generate_html_report(data)
        st.download_button(
            "下载报告",
            Path(path).read_bytes(),
            file_name=Path(path).name,
            mime="text/html",
        )


def page_processes() -> None:
    inject_scroll_page()
    page_heading("进程管理", "process")
    elevated = scanner.is_elevated()
    if elevated:
        st.success("当前以管理员/root 权限运行，可拦截他人进程")
    else:
        st.info(
            "当前为普通用户：只能终止自己的进程。拦截系统/他人进程请用下方命令以 root 启动控制台，"
            "或在终端 `sudo kill -TERM <PID>`"
        )
    limit = st.slider("条数", 20, 300, 100)
    only_high = st.checkbox("仅高危")
    if st.button("刷新") or st.session_state.proc_rows is None:
        st.session_state.proc_rows = scanner.list_processes(limit=limit)

    rows = st.session_state.proc_rows or []
    if only_high:
        rows = [r for r in rows if r.get("high_risk")]
    high = [r for r in (st.session_state.proc_rows or []) if r.get("high_risk")]

    if high:
        st.warning(f"{len(high)} 个高危相关进程")
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("#### 拦截")
    pid = st.number_input("PID", min_value=1, value=int(high[0]["pid"]) if high else 1)
    force = st.checkbox("强制拦截")
    if st.button("执行拦截", type="primary"):
        r = scanner.block_process(int(pid), force=force)
        if r["ok"]:
            st.success(r["message"])
            st.session_state.proc_rows = scanner.list_processes(limit=limit)
        else:
            st.error(r["message"])
            if r.get("needs_root") and r.get("hint"):
                st.code(r["hint"], language="bash")


def _events_display_df(events: list[dict]) -> pd.DataFrame:
    """事件表：等级 + 北京时间."""
    df = pd.DataFrame(events)
    if df.empty:
        return df
    df = df.copy()
    if "ts" in df.columns:
        df["时间"] = df["ts"].map(lambda x: format_display(x))
    if "level" in df.columns:
        level_map = {"严重": "!! 严重", "高": "! 高", "中": "· 中", "低": "低", "信息": "i 信息"}
        df["等级"] = df["level"].map(lambda x: level_map.get(str(x), str(x)))
    front = [c for c in ("时间", "等级") if c in df.columns]
    rest = [c for c in df.columns if c not in front and c not in ("level", "ts")]
    return df[front + rest]


def _render_monitor_panels(svc) -> None:
    flash = st.session_state.pop("_monitor_flash", None)
    if flash:
        st.success(flash)

    st.markdown(monitor_status_html(svc.running), unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("巡检次数", svc.tick_count if svc.running else "—")
    c2.metric("事件数", len(svc.get_events(500)))
    c3.metric("基线进程", svc.known_pid_count if svc.running else "—")
    c4.metric("巡检间隔", f"{svc.interval_sec:.0f}s" if svc.running else "—")

    tab_evt, tab_proc, tab_viz = st.tabs(["告警与事件", "进程快照", "多维态势"])
    with tab_evt:
        events = svc.get_events(200)
        with scroll_container(height=420):
            if events:
                st.dataframe(_events_display_df(events), width="stretch", hide_index=True)
            elif svc.running:
                st.info("监控运行中，约每 5 秒巡检；新进程会出现在此")
            else:
                st.info("点击「启动监控」开始记录")

        st.divider()
        st.caption("AIOps 测试 · 模拟 CPU 阈值触发（支持单核/多核压测）")

        col_cpu1, col_cpu2 = st.columns(2)
        with col_cpu1:
            if st.button("🔥 单核压测 (5秒)", key="test_high_cpu_btn", use_container_width=True):
                try:
                    import subprocess
                    from pathlib import Path

                    root = Path(__file__).resolve().parents[1]
                    res = subprocess.run(
                        ["bash", "scripts/stress_cpu.sh", "--duration", "5"],
                        cwd=root,
                        capture_output=True,
                        text=True,
                        timeout=45,
                    )
                    if res.returncode == 0:
                        st.success("✅ 单核压测完成！请到「报告中心」查看最新 cpu_report_*.html")
                        st.code(res.stdout.strip() or "执行成功")
                    else:
                        st.error(f"脚本返回码 {res.returncode}")
                        st.code(res.stderr or res.stdout)
                except Exception as exc:
                    st.error(f"触发失败: {exc}")

        with col_cpu2:
            if st.button("🔥🔥 多核压测 (10秒)", key="test_multi_cpu_btn", use_container_width=True):
                try:
                    import subprocess
                    from pathlib import Path

                    root = Path(__file__).resolve().parents[1]
                    with st.spinner("多核压测中... 请等待 10 秒"):
                        res = subprocess.run(
                            ["bash", "scripts/stress_cpu.sh", "--multi", "--duration", "10"],
                            cwd=root,
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                    if res.returncode == 0:
                        st.success("✅ 多核压测完成！报告包含各核心详细使用率")
                        st.code(res.stdout.strip() or "执行成功")
                    else:
                        st.error(f"脚本返回码 {res.returncode}")
                        st.code(res.stderr or res.stdout)
                except Exception as exc:
                    st.error(f"触发失败: {exc}")

        # 清理按钮
        if st.button("🧹 清理压测残留进程", key="cleanup_cpu_btn", type="secondary", use_container_width=True):
            try:
                import subprocess
                from pathlib import Path

                root = Path(__file__).resolve().parents[1]
                res = subprocess.run(
                    ["bash", "scripts/cleanup_stress.sh", "--quiet"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if res.returncode == 0:
                    st.info("✅ 清理完成")
                else:
                    st.warning("清理命令已执行")
            except Exception as exc:
                st.error(f"清理失败: {exc}")

    with tab_proc:
        snap = svc.get_process_snapshot(100)
        with scroll_container(height=420):
            if snap:
                df = pd.DataFrame(snap)
                high_n = sum(1 for r in snap if r.get("high_risk"))
                if high_n:
                    st.warning(f"快照中含 {high_n} 个高危相关进程")
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.caption("暂无快照")

    with tab_viz:
        events = svc.get_events(120)
        scan = st.session_state.get("last_scan") or {}
        risks = scan.get("risks") or []
        posture = risk_viz.posture_score(risks, events)
        pc1, pc2, pc3 = st.columns(3)
        pc1.metric("态势评分", f"{posture['score']}/100")
        pc2.metric("态势等级", posture["label"])
        pc3.metric("事件样本", len(events))
        st.caption("评分=近期扫描风险+监控事件加权；心跳不计入。自动刷新时本页约 5 秒更新。")

        dim_df = risk_viz.dimension_breakdown(risks, events)
        c_left, c_right = st.columns(2)
        with c_left:
            fig_r = risk_viz.fig_dimension_radar(dim_df)
            if fig_r:
                st.plotly_chart(fig_r, width="stretch", config=risk_viz.PLOTLY_STATIC_CONFIG)
            else:
                st.info("暂无分维度数据")
        with c_right:
            fig_b = risk_viz.fig_level_bars(posture.get("counts", {}))
            if fig_b:
                st.plotly_chart(fig_b, width="stretch", config=risk_viz.PLOTLY_STATIC_CONFIG)

        fig_t = risk_viz.fig_timeline(events)
        if fig_t:
            st.plotly_chart(fig_t, width="stretch", config=risk_viz.PLOTLY_STATIC_CONFIG)
        else:
            st.caption("时间线需有非心跳监控事件")

        points = risk_viz.merge_risks_and_events(risks, events)
        fig_c = risk_viz.fig_cube_3d(points, title="扫描 + 监控 三维分布")
        if fig_c:
            st.plotly_chart(fig_c, width="stretch", config=risk_viz.PLOTLY_STATIC_CONFIG)
        else:
            st.info("启动监控或执行扫描后显示三维点")


@st.fragment(run_every=timedelta(seconds=5))
def _monitor_auto_refresh() -> None:
    svc = get_monitor_service()
    if svc.running:
        _render_monitor_panels(svc)


def page_monitor() -> None:
    inject_scroll_page()
    page_heading("系统监控", "monitor")
    unread = get_unread_count()
    if unread > 0:
        st.markdown(
            f'<div class="alert-banner">有 <b>{unread}</b> 条未读离屏告警'
            f"（data/alerts/ · 终端: <code>uv run python scripts/alert_watch.py</code>）</div>",
            unsafe_allow_html=True,
        )
        if st.button("标记告警已读", key="mark_alerts_read"):
            mark_alerts_read()
            st.rerun()
    with st.expander("最近离屏告警", expanded=unread > 0):
        alerts = read_recent_alerts(20)
        if alerts:
            for a in alerts[:10]:
                st.markdown(f"`{a.get('level','')}` **{a.get('type','')}** — {a.get('message','')[:120]}")
        else:
            st.caption("暂无；启动监控后，严重/高 事件会写入 data/alerts/events.jsonl")
    svc = get_monitor_service()
    st.caption("P2：登录失败/暴破、监听端口变化、cron 变更；密码与密钥在界面自动打码")

    b1, b2, b3 = st.columns([1, 1, 2])
    if b1.button("启动监控", type="primary", disabled=svc.running, use_container_width=True):
        st.session_state._monitor_flash = svc.start()
        st.rerun()
    if b2.button("停止监控", disabled=not svc.running, use_container_width=True):
        st.session_state._monitor_flash = svc.stop()
        st.rerun()
    b3.caption("侧栏「启动/停止监控」不跳转页面；勾选自动刷新每 5 秒更新下方数据")

    auto = st.checkbox("自动刷新（5 秒）", value=svc.running, key="monitor_auto_refresh")

    if auto and svc.running:
        _monitor_auto_refresh()
    else:
        _render_monitor_panels(svc)


# 工具调用图标映射
_TOOL_ICONS: dict[str, str] = {
    "query_security_scan": "🔍", "query_security_scan_json": "🔍",
    "list_processes": "⚙", "run_full_security_check": "🏥",
    "generate_security_report": "📋", "get_system_health": "📊",
    "start_monitor": "▶", "stop_monitor": "⏹", "get_monitor_events": "📡",
    "get_audit_log": "📝", "search_security_knowledge": "📚",
    "get_grounded_advice": "💡", "check_exposed_ports": "🌐",
    "block_high_risk_process": "🚫", "get_process_detail": "🔎",
    "list_network_connections": "🌐", "check_sensitive_paths": "📁",
    "run_terminal_command": "💻", "run_autonomous_mission": "🤖",
    "run_risk_demo": "🎯", "build_knowledge_index": "📦",
}

# Skill 工具图标
_SKILL_ICONS: dict[str, str] = {
    "health_": "🏥", "log_": "📄", "hardening_": "🛡", "config_": "⚙",
    "incident_": "🚑",
}


def _tool_icon(name: str) -> str:
    if name in _TOOL_ICONS:
        return _TOOL_ICONS[name]
    for prefix, icon in _SKILL_ICONS.items():
        if name.startswith(prefix):
            return icon
    return "🔧"


# 终端命令白话映射
_CMD_DESCRIPTIONS: dict[str, str] = {
    "last": "SSH/终端登录历史",
    "lastb": "SSH 爆破失败记录",
    "who": "当前 SSH 在线用户",
    "sshd": "SSH 认证日志",
    "grep": "日志关键词搜索",
    "journalctl": "系统服务日志",
    "lastlog": "所有用户 SSH 登录记录",
    "ps aux": "进程快照",
    "netstat": "网络连接",
    "ss ": "监听端口",
    "df -": "磁盘使用",
    "free": "内存使用",
    "uptime": "系统运行时间",
    "top": "CPU/内存排行",
}


def _cmd_summary(raw: str) -> str:
    """将长 shell 命令转为白话描述."""
    cmd = raw.strip()
    for key, desc in _CMD_DESCRIPTIONS.items():
        if key in cmd:
            return desc
    # 取管道前半部分作为摘要
    if "|" in cmd:
        return cmd.split("|")[0].strip()[:30]
    return cmd[:30]


def _summarize_terminal_output(command: str, output: str) -> str:
    """从终端命令输出中提取一行关键摘要（面向非专业用户）."""
    if not output or output == "（无输出）":
        return "无输出"
    cmd = command.strip()
    lines = [l for l in output.split("\n") if l.strip()]
    if not lines:
        return "无输出"

    # last -n / last -i / lastlog → SSH/终端登录记录摘要
    if cmd.startswith("last") or "lastlog" in cmd:
        # 解析行数
        user_entries = []
        for l in lines:
            if not l or l.startswith(" ") or "wtmp" in l or "btmp" in l:
                continue
            parts = l.split()
            if len(parts) >= 1 and parts[0][0].isalpha() and parts[0] != "Username":
                user_entries.append(parts[0])
        unique = list(dict.fromkeys(user_entries))
        unique = [u for u in unique if u not in ("reboot", "shutdown")]
        # 提取最新一条
        latest_line = ""
        for l in lines:
            if not l or l.startswith(" ") or "wtmp" in l or "btmp" in l:
                continue
            parts = l.split()
            if len(parts) >= 3:
                latest_line = f"{parts[0]}({parts[-2] if len(parts) > 3 else '?'} {parts[2] if len(parts) > 2 else '?'})"
                break
        if "lastb" in cmd:
            fail_count = len([l for l in lines if l.strip() and not l.startswith(" ") and "btmp" not in l])
            if fail_count == 0:
                return "无 SSH 爆破尝试"
            return f"❌ SSH爆破 {fail_count}次 · {latest_line}" if latest_line else f"❌ SSH爆破 {fail_count}次"
        if "lastlog" in cmd:
            users = unique[:4]
            suffix = f" 等{len(unique)}用户" if len(unique) > 4 else ""
            return f"📋 所有用户最新SSH登录 · {' '.join(users)}{suffix}"
        # last
        total = len([l for l in lines if l.strip() and not l.startswith(" ") and "wtmp" not in l])
        return f"📜 SSH/终端登录历史 {total}条 · {latest_line}" if latest_line else f"📜 SSH/终端登录历史 {total}条"

    # who → 当前 SSH/终端在线用户
    if cmd.startswith("who"):
        online = len([l for l in lines if l.strip()])
        if online == 0:
            return "无在线用户"
        first = lines[0].split() if lines else []
        detail = f"{first[0]} {first[1]}" if len(first) >= 2 else ""
        return f"👤 当前SSH在线 {online}人 · {detail}" if detail else f"👤 当前SSH在线 {online}人"

    # sshd / journalctl → SSH 认证日志
    if "sshd" in cmd or "journalctl" in cmd:
        fail_count = len([l for l in lines if "Failed" in l or "failure" in l.lower()])
        accepted = len([l for l in lines if "Accepted" in l])
        parts = []
        if accepted:
            parts.append(f"✅ 成功 {accepted}")
        if fail_count:
            parts.append(f"❌ 失败 {fail_count}")
        total = len(lines)
        return f"📄 SSH认证日志 {total}行 · {' '.join(parts)}" if parts else f"📄 SSH认证日志 {total}行"

    # ps / top → 进程快照
    if cmd.startswith("ps ") or cmd.startswith("top "):
        total = len([l for l in lines if l.strip() and not l.startswith("PID") and not l.startswith("top")])
        return f"⚙ 进程 {total}个"

    # df → 磁盘
    if cmd.startswith("df "):
        # 找 / 分区
        for l in lines:
            if l.startswith("/"):
                parts = l.split()
                if len(parts) >= 5:
                    return f"💾 磁盘 / {parts[4] if len(parts) > 4 else '?'} 使用率"
        return "💾 磁盘使用"

    # free → 内存
    if cmd.startswith("free"):
        for l in lines:
            if l.lower().startswith("mem"):
                parts = l.split()
                if len(parts) >= 3:
                    used = parts[2]
                    total = parts[1]
                    return f"🧠 内存 {used}/{total}"

    # uptime
    if cmd.startswith("uptime"):
        first = lines[0] if lines else ""
        return f"⏱ {first[:50]}"

    # netstat / ss
    if cmd.startswith("ss ") or cmd.startswith("netstat"):
        listen = len([l for l in lines if "LISTEN" in l])
        return f"🌐 端口 · 监听 {listen}个"

    # grep 通用
    if cmd.startswith("grep"):
        match_count = len(lines)
        return f"🔍 匹配 {match_count}行"

    # 默认取输出前 40 字
    preview = output.replace("\n", " ").strip()[:40]
    if len(output) > 40:
        preview += "..."
    return f"📄 {preview}"


def _render_tool_flow(tool_trace: list[dict]) -> None:
    """渲染工具调用流程时间线（面向所有用户）."""
    tools = [t for t in tool_trace if t.get("tool")]
    if not tools:
        return

    # 合并连续的终端命令为一组
    merged: list[dict] = []
    terminal_group: list[dict] = []
    for t in tools:
        name = t.get("tool", "")
        if name == "run_terminal_command":
            terminal_group.append(t)
        else:
            if terminal_group:
                merged.append({"type": "terminal_group", "items": terminal_group})
                terminal_group = []
            merged.append({"type": "single", "item": t})
    if terminal_group:
        merged.append({"type": "terminal_group", "items": terminal_group})

    st.markdown(
        '<p style="color:#90a4ae;font-size:0.78rem;margin:0.3rem 0 0.15rem 0;">'
        '工具调用流程</p>',
        unsafe_allow_html=True,
    )

    cards_html = []
    for entry in merged:
        if entry["type"] == "single":
            t = entry["item"]
            name = t.get("tool", "")
            args = t.get("args", {})
            icon = _tool_icon(name)
            args_str = ""
            if args:
                parts = [f"{k}={v}" for k, v in list(args.items())[:2]]
                args_str = f" ({', '.join(parts)})"
            output = t.get("output", "")
            output_brief = output[:60].replace("\n", " ") if output else ""
            if len(output) > 60:
                output_brief += "..."
            cards_html.append(
                f'<div style="display:flex;align-items:center;gap:0.4rem;'
                f'padding:3px 0;font-size:0.82rem;">'
                f'<span style="color:#64b5f6;">{icon}</span>'
                f'<code style="background:#1a2332;padding:1px 4px;border-radius:3px;'
                f'font-size:0.75rem;">{name}{args_str}</code>'
                f'<span style="color:#78909c;font-size:0.75rem;">→ {output_brief}</span>'
                f'</div>'
            )
        else:
            # 终端命令组：标题行 + 每条命令的摘要
            items = entry["items"]
            group_lines = [
                f'<div style="display:flex;align-items:center;gap:0.4rem;'
                f'padding:2px 0;font-size:0.82rem;">'
                f'<span style="color:#64b5f6;">💻</span>'
                f'<span style="color:#e3f2fd;font-size:0.78rem;">终端采集</span>'
                f'<span style="color:#78909c;font-size:0.72rem;">（{len(items)} 条命令）</span>'
                f'</div>'
            ]
            # 每条命令一行摘要（最多显示 6 条，超出折叠）
            max_show = 6
            show_items = items[:max_show]
            for idx, it in enumerate(show_items):
                cmd = it.get("args", {}).get("command", "")
                output = it.get("output", "")
                cmd_brief = _cmd_summary(cmd)
                data_summary = _summarize_terminal_output(cmd, output)
                is_last = (idx == len(show_items) - 1) and len(items) <= max_show
                connector = "└" if is_last or (idx == len(show_items) - 1 and len(items) > max_show) else "├"
                group_lines.append(
                    f'<div style="display:flex;align-items:center;gap:0.3rem;'
                    f'padding:1px 0 1px 0.8rem;font-size:0.78rem;">'
                    f'<span style="color:#546e7a;font-size:0.65rem;">{connector}</span>'
                    f'<span style="color:#90a4ae;font-size:0.72rem;">{cmd_brief}</span>'
                    f'<span style="color:#b0bec5;font-size:0.72rem;">→</span>'
                    f'<span style="color:#e3f2fd;font-size:0.75rem;">{data_summary}</span>'
                    f'</div>'
                )
            if len(items) > max_show:
                group_lines.append(
                    f'<div style="display:flex;align-items:center;gap:0.3rem;'
                    f'padding:1px 0 1px 0.8rem;font-size:0.78rem;">'
                    f'<span style="color:#546e7a;font-size:0.65rem;">└</span>'
                    f'<span style="color:#78909c;font-size:0.72rem;">… 还有 {len(items) - max_show} 条命令已折叠</span>'
                    f'</div>'
                )
            cards_html.append("\n".join(group_lines))

    st.markdown("\n".join(cards_html), unsafe_allow_html=True)


def _submit_chat(brain, text: str) -> None:
    st.session_state.chat_messages.append({"role": "user", "content": text})
    with st.spinner("Agent 思考中…"):
        result = asyncio.run(brain.chat(text))

    # 追踪成本
    token_usage = result.get("token_usage", {})
    model_used = result.get("model_used", "")
    cost_cny = 0.0
    if token_usage and token_usage.get("total_tokens", 0) > 0:
        cost = state.get_cost_tracker().add_from_usage(model_used, token_usage)
        cost_cny = cost.total_cost_cny
    else:
        cost_cny = 0.0

    st.session_state.chat_messages.append(
        {
            "role": "assistant",
            "content": result.get("reply", ""),
            "tools": result.get("tool_trace"),
            "plan": result.get("plan"),
            "auto_warn": result.get("auto_warn"),
            "token_usage": token_usage,
            "model_used": model_used,
            "cost_cny": cost_cny,
        }
    )


def page_chat() -> None:
    inject_chat_layout()
    page_heading("智能助手", "chat")
    if not config.llm_configured():
        st.error("请在 .env 中配置 LLM_API_KEY 后执行 boot_stop → boot_start")
        return
    brain = state.get_brain()
    if not brain:
        st.error("Agent 初始化失败")
        return

    # 清除对话按钮
    col_chat_hdr1, col_chat_hdr2 = st.columns([4, 1])
    with col_chat_hdr2:
        if st.button("🗑 清除对话", use_container_width=True, key="clear_chat"):
            st.session_state.chat_messages = []
            brain.reset()
            st.rerun()

    st.checkbox(
        "确认高危操作（拦截进程、写操作终端等）",
        key="tool_user_confirmed",
        help="勾选后，Agent 才可执行 block_high_risk_process 等需确认的工具",
    )
    # 同步到 brain（checkbox 变更后 get_brain 会更新 executor）
    state.get_brain()

    with st.expander("说明与规则", expanded=False):
        st.caption(f"{AUTOMATION_LEVEL['level']} · 侧栏与下方均可快捷提问")

    render_chat_page_shortcuts()

    # 对话历史：固定高度滚动，避免把底部输入顶出视口
    with scroll_container(height=420):
        if not st.session_state.chat_messages:
            st.caption("↓ 在屏幕最底部输入框提问")
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                if msg.get("auto_warn"):
                    st.warning("检测到高/严重风险")
                st.markdown(safe_markdown(msg["content"]))
                # 工具调用流程可视化（所有用户可见）
                if msg.get("tools"):
                    _render_tool_flow(msg["tools"])
                # Token 和成本信息（只在有数据时显示）
                usage = msg.get("token_usage", {})
                if usage and usage.get("total_tokens", 0) > 0:
                    total_tokens = usage.get('total_tokens', 0)
                    cost_cny = msg.get("cost_cny", 0) or 0

                    # 如果没有缓存的成本，重新计算
                    if not cost_cny and msg.get("model_used"):
                        cost = estimate_cost(
                            model=msg.get("model_used"),
                            input_tokens=usage.get('prompt_tokens', 0),
                            output_tokens=usage.get('completion_tokens', 0),
                        )
                        cost_cny = cost.total_cost_cny

                    cost_str = format_cost_for_display(cost_cny)

                    # 构建显示信息
                    info_parts = [f"📝 {total_tokens:,} tokens · 💰 {cost_str}"]

                    # 显示 fallback 触发
                    if msg.get("fallback_used"):
                        fallback_model = msg.get("fallback_metadata", {}).get("fallback_model", "备用模型")
                        info_parts.append(f"🔄 已回退到 {fallback_model[:15]}")

                    # 紧凑格式显示
                    st.caption(" · ".join(info_parts))
                # 调试模式：显示原始 JSON
                if st.session_state.get("_debug_mode") and (msg.get("tools") or msg.get("plan")):
                    with st.expander("⚙ 原始数据（调试）", expanded=False):
                        if msg.get("plan"):
                            st.code(json.dumps(safe_json_data(msg["plan"]), ensure_ascii=False, indent=2), language="json")
                        if msg.get("tools"):
                            st.code(json.dumps(safe_json_data(msg["tools"]), ensure_ascii=False, indent=2), language="json")

    queued = st.session_state.pop("_chat_queue", None) or st.session_state.pop("_pending", None)
    if queued:
        _submit_chat(brain, queued)
        st.rerun()

    user_input = st.chat_input("输入安全运维指令…", key="main_chat_input")
    if user_input:
        _submit_chat(brain, user_input)
        st.rerun()


def page_reports() -> None:
    from ui.report_preview import load_report_json, render_report_html, wrap_report_for_preview

    inject_scroll_page()

    page_heading("报告中心", "report")
    st.caption("报告为浅色主题，便于阅读；预览区已适配深色控制台背景")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(REPORTS_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)

    if st.button("基于最新扫描生成报告", type="primary"):
        data = st.session_state.last_scan or state.run_scan()
        path = scanner.generate_html_report(data)
        st.success(f"已生成: {path}")
        st.rerun()

    if not files:
        st.info("暂无报告，请先在「安全扫描」执行扫描后生成")
        return

    names = [f.name for f in files]
    sel = st.selectbox("选择报告", names)
    path = REPORTS_DIR / sel
    st_info = path.stat()
    st.caption(
        f"大小 {st_info.st_size // 1024} KB · {format_file_mtime(path)} · {TZ_LABEL}"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "下载 HTML",
            path.read_bytes(),
            file_name=sel,
            mime="text/html",
            use_container_width=True,
        )
    with col2:
        if st.button("删除此报告", use_container_width=True):
            path.unlink(missing_ok=True)
            path.with_suffix(".json").unlink(missing_ok=True)
            st.rerun()

    tab_table, tab_html = st.tabs(["表格视图（推荐）", "网页预览"])

    with tab_table:
        data = load_report_json(path)
        if data and data.get("risks"):
            st.dataframe(
                _risks_df(data["risks"]),
                use_container_width=True,
                hide_index=True,
            )
        elif data:
            st.success("该次扫描未发现风险项")
            st.json(
                {
                    "platform": data.get("platform"),
                    "scanned_at": data.get("scanned_at"),
                    "scanned_at_display": format_display(data.get("scanned_at")),
                }
            )
        else:
            st.info("旧版报告无 JSON 数据，请重新生成报告，或使用「网页预览」")

    with tab_html:
        try:
            preview = wrap_report_for_preview(path.read_text(encoding="utf-8"))
            render_report_html(preview, height=600)
        except Exception as exc:  # noqa: BLE001
            st.error(f"报告预览失败: {exc}")
            st.caption("请使用「表格视图」或重新生成报告")


def page_audit() -> None:
    inject_scroll_page()
    page_heading("审计日志", "audit")
    limit = st.slider("条数", 20, 500, 100)
    records = safe_json_data(read_audit_tail(limit))
    if not records:
        st.info("暂无记录")
        return
    df = pd.DataFrame(records)
    if "ts" in df.columns:
        df = df.copy()
        df["时间"] = df["ts"].map(lambda x: format_display(x))
        cols = ["时间"] + [c for c in df.columns if c not in ("时间", "ts")]
        df = df[cols]
    actions = ["全部"] + sorted(df["action"].dropna().unique().tolist())
    filt = st.selectbox("筛选", actions)
    if filt != "全部":
        df = df[df["action"] == filt]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "导出 JSON",
        json.dumps(records, ensure_ascii=False, indent=2),
        file_name=f"audit_{now_filename_ts()}.json",
        mime="application/json",
    )


def _page_autonomous():
    from ui.pages_autonomous import page_autonomous

    page_autonomous()


def _page_risk_demo():
    from ui.pages_demo import page_risk_demo

    page_risk_demo()


def _page_confirm():
    from ui.pages_confirm import page_confirm

    page_confirm()


def _page_skills():
    from ui.pages_skills import page_skills

    page_skills()


def _page_skill_flows():
    from ui.pages_skill_flows import page_skill_flows

    page_skill_flows()


def _page_knowledge():
    from ui.pages_knowledge import page_knowledge

    page_knowledge()


PAGES = {
    "总览": page_overview,
    "自主运维": _page_autonomous,
    "安全扫描": page_scan,
    "进程管理": page_processes,
    "系统监控": page_monitor,
    "风险演练": _page_risk_demo,
    "Skill 插件": _page_skills,
    "Skill 流程": _page_skill_flows,
    "知识库": _page_knowledge,
    "安全确认": _page_confirm,
    "智能助手": page_chat,
    "报告中心": page_reports,
    "审计日志": page_audit,
}

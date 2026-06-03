"""风险演练中心 — 本地模拟、边界测试、立体化视图."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from security_agent.demo.boundary import run_terminal_boundary_tests, summarize_boundary
from security_agent.demo.fixture_catalog import DETECTION_FIXTURES, FIXTURE_CATEGORIES
from security_agent.demo.scenarios import SCENARIO_META
from security_agent.demo.service import get_demo_service
from security_agent.rules.engine import check_terminal
from security_agent.terminal.executor import run_terminal_sync
from ui.icons import page_heading
from ui.layout import inject_scroll_page, scroll_container
from ui import risk_viz



def _sync_cube_scan(scan: dict | None) -> None:
    if scan:
        st.session_state.demo_cube_scan = scan


def _load_cube_scan(svc, source: str) -> dict | None:
    if source == "上次场景结果":
        last = st.session_state.get("demo_last") or {}
        return last.get("scan")
    if source == "即时合成数据":
        return svc.build_synthetic_scan()
    if source == "合并扫描(实盘+合成)":
        return svc.merge_scan()
    return None


def _render_cube_3d(scan: dict, *, chart_key: str, chart_height: int) -> None:
    points = scan.get("cube_points") or risk_viz.risks_to_cube_points(scan.get("risks") or [])
    if not points:
        st.info("暂无立体化数据点")
        return
    fig = risk_viz.fig_cube_3d(points, title="风险立体分布（类型 × 严重度 × 来源）")
    if fig is None:
        return
    fig.update_layout(height=chart_height, autosize=True)
    st.plotly_chart(
        fig,
        width="stretch",
        key=chart_key,
        config=risk_viz.PLOTLY_STATIC_CONFIG,
    )


def _render_cube_bars(scan: dict) -> None:
    points = scan.get("cube_points") or risk_viz.risks_to_cube_points(scan.get("risks") or [])
    if not points:
        return
    df = pd.DataFrame(points)
    c1, c2 = st.columns(2)
    with c1:
        layer_counts = df.groupby("layer").size().reset_index(name="count")
        st.caption("按层级")
        st.bar_chart(layer_counts.set_index("layer"), height=220)
    with c2:
        st.caption("按等级")
        lvl = df.groupby("level").size().reset_index(name="count")
        st.bar_chart(lvl.set_index("level"), height=220)


def page_risk_demo() -> None:
    inject_scroll_page()
    page_heading("风险演练中心", "demo")
    st.caption(
        f"内置 **{len(DETECTION_FIXTURES)}** 条检测校准 + **30+** 条终端边界用例；"
        "立体图请用「立体态势」页并点击「刷新图表」。"
    )

    svc = get_demo_service()
    tab_scenario, tab_cal, tab_boundary, tab_terminal, tab_cube = st.tabs(
        ["场景演练", "校准用例库", "规则边界", "单条命令试探", "立体态势"]
    )

    with tab_scenario:
        with st.expander("场景说明", expanded=False):
            for sid, meta in SCENARIO_META.items():
                st.markdown(f"**{meta['title']}** (`{sid}`) — {meta['desc']}")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            scenario = st.selectbox(
                "选择场景",
                list(SCENARIO_META.keys()),
                format_func=lambda x: SCENARIO_META[x]["title"],
                key="demo_scenario_select",
            )
        with c2:
            tool = st.selectbox(
                "诱饵工具名",
                ["nmap", "nc", "ncat", "hydra", "sqlmap"],
                key="demo_tool_select",
            )
        with c3:
            st.write("")
            st.write("")
            run_btn = st.button("运行场景", type="primary", use_container_width=True, key="demo_run_scenario")

        c4, c5, c6, c7 = st.columns(4)
        with c4:
            if st.button("仅注入合成数据", use_container_width=True, key="demo_synth_only"):
                scan = svc.build_synthetic_scan()
                st.session_state.demo_last = {"ok": True, "scan": scan}
                _sync_cube_scan(scan)
                st.rerun()
        with c5:
            if st.button("停止所有诱饵", use_container_width=True, key="demo_stop_decoy"):
                st.session_state.demo_last = {"ok": True, "decoy": svc.stop_decoys()}
                st.rerun()
        with c6:
            label = "⏳ CPU 压测中…" if svc.is_stressing() else "CPU 压测"
            if st.button(label, use_container_width=True, key="demo_cpu_stress", disabled=svc.is_stressing()):
                with st.spinner("压测中（CPU 爬升约需 8 秒）…"):
                    result = svc.run_cpu_stress()
                    st.session_state.demo_last = result
                    if result.get("scan"):
                        _sync_cube_scan(result["scan"])
                st.rerun()
        with c7:
            if st.button("停止压测", use_container_width=True, key="demo_stop_stress"):
                st.session_state.demo_last = {"ok": True, "stress_stop": svc.stop_cpu_stress()}
                st.rerun()

        if run_btn:
            with st.spinner("演练中…"):
                result = svc.run_scenario(scenario, simulate_tool=tool)
                st.session_state.demo_last = result
                if result.get("scan"):
                    _sync_cube_scan(result["scan"])
            st.rerun()

        last = st.session_state.get("demo_last")
        with scroll_container(height=480):
            if not last:
                st.info("选择场景后点击「运行场景」；推荐先跑「检测规则校准（66 用例）」")
            elif last.get("calibration"):
                cal = last["calibration"]
                s = cal["summary"]
                st.success(
                    f"校准准确率 {s['accuracy_pct']}% · 误报 {s['false_positive']} · 漏报 {s['false_negative']}"
                )
                failed = cal.get("failed_cases", [])
                if failed:
                    st.dataframe(pd.DataFrame(failed), width="stretch", hide_index=True)
            else:
                if last.get("decoy"):
                    st.success(str(last["decoy"].get("message", last["decoy"])))
                if last.get("boundary"):
                    s = last["boundary"]["summary"]
                    st.metric("边界用例通过率", f"{s['pass_rate']}%", f"{s['passed']}/{s['total']}")
                    st.dataframe(
                        pd.DataFrame(last["boundary"]["cases"]),
                        width="stretch",
                        hide_index=True,
                    )
                if last.get("cpu_stress"):
                    cs = last["cpu_stress"]
                    if cs.get("ok"):
                        st.success(cs.get("message", "CPU 压测完成"))
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("压测前 CPU", f"{cs.get('cpu_before', 0):.0f}%")
                        m2.metric("压测中 CPU", f"{cs.get('cpu_during', 0):.0f}%")
                        m3.metric("CPU 峰值", f"{cs.get('cpu_peak', 0):.0f}%", delta_color="inverse")
                        m4.metric("触发告警", cs.get("alarm_count", 0))
                        alarms = cs.get("alarms", [])
                        if alarms:
                            with st.expander(f"监控告警明细（共 {len(alarms)} 条）", expanded=False):
                                st.dataframe(
                                    pd.DataFrame(
                                        [
                                            {"时间": a.get("ts", ""), "等级": a.get("level"),
                                             "CPU%": a.get("cpu_percent", "?"), "消息": (a.get("message") or "")[:100]}
                                            for a in alarms
                                        ]
                                    ),
                                    width="stretch",
                                    hide_index=True,
                                )
                    else:
                        st.warning(cs.get("error", "CPU 压测失败"))
                if last.get("stress_stop"):
                    ss = last["stress_stop"]
                    st.info(ss.get("message", "已停止压测"))
                if last.get("scan"):
                    scan = last["scan"]
                    st.markdown(
                        f"**风险项 {scan.get('risk_count', 0)}** · "
                        f"实盘 {scan.get('live_count', '-')} · 合成 {scan.get('synthetic_count', '-')}"
                    )
                    st.caption("立体图已同步，请切换到「立体态势」查看。")
                    risks = scan.get("risks", [])
                    if risks:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "等级": r.get("level"),
                                        "类型": r.get("type"),
                                        "来源": r.get("source", "live"),
                                        "层级": r.get("layer", "检测"),
                                        "对象": r.get("name") or r.get("path", ""),
                                        "说明": (r.get("message") or "")[:120],
                                    }
                                    for r in risks
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                    st.download_button(
                        "导出演练 JSON",
                        json.dumps(scan, ensure_ascii=False, indent=2),
                        file_name="risk_demo_scan.json",
                        mime="application/json",
                        key="demo_download_scan",
                    )

    with tab_cal:
        cats = ["all"] + list(FIXTURE_CATEGORIES.keys())
        cat = st.selectbox(
            "分类筛选",
            cats,
            format_func=lambda x: "全部" if x == "all" else f"{x} — {FIXTURE_CATEGORIES.get(x, x)}",
            key="demo_cal_cat",
        )
        c1, c2 = st.columns(2)
        if c1.button("运行检测校准", type="primary", use_container_width=True, key="demo_run_cal"):
            with st.spinner("校准中…"):
                st.session_state.demo_calibration = svc.run_fixture_calibration(
                    None if cat == "all" else cat
                )
            st.rerun()
        if c2.button("查看用例清单", use_container_width=True, key="demo_show_catalog"):
            st.session_state.demo_catalog = svc.get_fixture_catalog()
            st.rerun()

        cal = st.session_state.get("demo_calibration")
        with scroll_container(height=520):
            if cal:
                s = cal["summary"]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("准确率", f"{s['accuracy_pct']}%")
                m2.metric("精确率", f"{s['precision_pct']}%")
                m3.metric("召回率", f"{s['recall_pct']}%")
                m4.metric("失败", s["failed"])
                show_fail = st.checkbox("仅显示失败用例", value=bool(cal.get("failed_cases")), key="demo_cal_fail_only")
                rows = cal["failed_cases"] if show_fail else cal["results"]
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                st.download_button(
                    "导出校准报告",
                    json.dumps(cal, ensure_ascii=False, indent=2),
                    file_name="detection_calibration.json",
                    mime="application/json",
                    key="demo_download_cal",
                )
            else:
                st.info("点击「运行检测校准」验证当前规则；开发改检测逻辑后应重新跑一遍。")

            catalog = st.session_state.get("demo_catalog")
            if catalog:
                with st.expander(f"用例库目录（共 {catalog['total']} 条）", expanded=False):
                    for ckey, items in catalog.get("fixtures_by_category", {}).items():
                        st.markdown(f"**{FIXTURE_CATEGORIES.get(ckey, ckey)}** ({len(items)})")
                        st.dataframe(pd.DataFrame(items), width="stretch", hide_index=True)

    with tab_boundary:
        if st.button("运行全部边界用例", type="primary", key="demo_run_boundary"):
            rows = run_terminal_boundary_tests()
            st.session_state.demo_boundary = {"cases": rows, "summary": summarize_boundary(rows)}
            st.rerun()
        pack = st.session_state.get("demo_boundary")
        with scroll_container(height=520):
            if pack:
                s = pack["summary"]
                m1, m2, m3 = st.columns(3)
                m1.metric("总计", s["total"])
                m2.metric("通过", s["passed"])
                m3.metric("失败", s["failed"])
                st.dataframe(pd.DataFrame(pack["cases"]), width="stretch", hide_index=True)
            else:
                st.info("点击按钮运行终端/工具规则矩阵（约 35 条，不执行 shell）")

    with tab_terminal:
        st.caption("试探单条命令的规则裁决；勾选确认后才会真正执行（仅允许/已确认类）。")
        cmd = st.text_input("命令", value="ps aux | head -3", key="demo_term_cmd")
        confirmed = st.checkbox("用户已确认（kill 等）", value=False, key="demo_term_confirm")
        c1, c2 = st.columns(2)
        if c1.button("仅检查规则", key="demo_check_only"):
            r = check_terminal(cmd, user_confirmed=confirmed)
            st.json({"verdict": r.verdict.value, "reason": r.reason, "rule_id": r.rule_id})
        if c2.button("检查并尝试执行", key="demo_run_cmd"):
            r = check_terminal(cmd, user_confirmed=confirmed)
            st.write(f"规则: **{r.verdict.value}** — {r.reason}")
            if r.verdict.value == "allow":
                with scroll_container(height=240):
                    out = run_terminal_sync(cmd, user_confirmed=confirmed, timeout_sec=15.0)
                    st.code(out.to_text())

    with tab_cube:
        src = st.radio(
            "数据来源",
            ["上次场景结果", "即时合成数据", "合并扫描(实盘+合成)"],
            horizontal=True,
            key="demo_cube_source",
        )
        b1, b2, b3 = st.columns([1, 1, 2])
        refresh = b1.button("刷新图表", type="primary", use_container_width=True, key="demo_cube_refresh")
        if b2.button("清空缓存", use_container_width=True, key="demo_cube_clear"):
            st.session_state.pop("demo_cube_scan", None)
            st.rerun()

        if refresh:
            with st.spinner("生成图表数据…"):
                loaded = _load_cube_scan(svc, src)
                if loaded:
                    _sync_cube_scan(loaded)
                else:
                    st.session_state.pop("demo_cube_scan", None)
                st.session_state.demo_cube_rev = st.session_state.get("demo_cube_rev", 0) + 1
            st.rerun()

        scan = st.session_state.get("demo_cube_scan")
        if scan is None and src == "上次场景结果":
            last_scan = (st.session_state.get("demo_last") or {}).get("scan")
            if last_scan:
                scan = last_scan
                _sync_cube_scan(scan)

        if scan:
            b3.caption(
                f"风险 {scan.get('risk_count', 0)} 项 · "
                f"数据点 {len(scan.get('cube_points') or [])} · 来源: {src}"
            )
            st.markdown("#### 三维分布")
            chart_h = st.slider(
                "3D 区域高度",
                min_value=320,
                max_value=720,
                value=int(st.session_state.get("demo_cube_height", 450)),
                step=30,
                key="demo_cube_height_slider",
            )
            st.session_state.demo_cube_height = chart_h
            rev = st.session_state.get("demo_cube_rev", 0)
            _render_cube_3d(
                scan,
                chart_key=f"demo_cube_3d_{src}_{rev}_{chart_h}",
                chart_height=chart_h,
            )
            st.markdown("#### 统计柱状图")
            _render_cube_bars(scan)
        else:
            st.info(
                "请先点击 **「刷新图表」**，或在「场景演练」运行场景后再来。"
                "（仅切换数据来源不会自动加载，避免误触发全机扫描。）"
            )

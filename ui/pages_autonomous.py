"""自主运维页面."""

from __future__ import annotations

import asyncio

import pandas as pd
import streamlit as st

from security_agent import config
from security_agent.agent.autonomous import AutonomousAgent
from security_agent.rules.engine import RuleVerdict, check_terminal
from security_agent.terminal.executor import run_terminal_sync
from security_agent.workflow.engine import WorkflowState
from ui.icons import page_heading
from ui.layout import inject_scroll_page, scroll_container
from security_agent.timeutil import TZ_LABEL, format_display
from ui.safe_display import safe_markdown


def page_autonomous() -> None:
    """自主运维页面 - A2赛题核心功能演示.
    
    支持场景:
    1. "帮我清理系统垃圾" → 感知环境 → 识别大日志文件 → 安全校验 → 受限执行
    2. "检查系统安全" → 扫描风险 → 生成报告
    3. "分析登录异常" → 审计日志 → 根因分析
    """
    inject_scroll_page()
    page_heading("自主运维", "autonomous")
    st.caption("A2赛题核心: 自然语言 → OS感知 → 安全校验 → 受限执行 → 链路溯源")

    # A2赛题场景引导
    with st.expander("📖 A2赛题核心场景演示指南", expanded=not config.llm_configured()):
        st.markdown("""
        **赛题核心场景**: 用户说"帮我清理系统垃圾" → Agent自动完成以下闭环:
        
        ```
        1. 接收指令 → 自然语言理解任务目标
        2. 感知环境 → 调用df/du/find等工具定位大日志文件
        3. 安全校验 → 规则引擎识别是否为关键数据库日志
        4. 权限评估 → 确认当前权限是否合规(非root不执行高危操作)
        5. 受限执行 → 仅删除安全的/tmp和轮转日志
        6. 链路溯源 → 完整记录「指令→感知→决策→校验→执行」日志
        ```
        
        **使用步骤**:
        1. 在下方输入任务目标（如"清理系统垃圾并生成报告"）
        2. 如需执行kill/sudo等高危操作，勾选「允许高危命令」
        3. 点击「启动自主任务」→ Agent自动规划并执行
        4. 如需人工确认的任务，会停在「等待确认」状态
        5. 点击「继续执行（已确认）」完成剩余步骤
        6. 在「任务结果」页查看完整执行链路
        """)
        st.info("💡 首次使用建议先勾选「仅生成计划」，查看Agent的规划是否合理")
    
    if not config.llm_configured():
        st.error("请在 .env 配置 LLM_API_KEY 后 boot_stop → boot_start")
        return

    if "autonomous_agent" not in st.session_state:
        st.session_state.autonomous_agent = AutonomousAgent()
    agent: AutonomousAgent = st.session_state.autonomous_agent

    tab_task, tab_term, tab_result = st.tabs(["🎯 自主任务", "💻 终端", "📋 任务结果"])

    with tab_task:
        # A2赛题安全等级展示
        info = agent.automation_info()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("自动化等级", info.get("level", "L3")[:12], help="L1=全人工 L2=辅助 L3=半自动 L4=全自动")
        c2.metric("安全门控", "✓ 启用", help="规则引擎实时校验每条指令")
        c3.metric("权限隔离", "✓ 启用", help="高危操作需确认/降权执行")
        c4.metric("链路溯源", "✓ 启用", help="全流程审计日志记录")
        
        st.divider()
        
        # A2赛题典型场景快捷输入
        st.caption("🎯 A2赛题典型场景（点击填充）")
        scenario_cols = st.columns(3)
        scenarios = [
            ("清理系统垃圾", "帮我清理系统垃圾，删除大日志文件和临时文件，生成清理报告"),
            ("检查系统安全", "全面检查系统安全风险，扫描高危进程和暴露端口，生成安全报告"),
            ("分析登录异常", "分析最近登录失败记录，识别是否有暴力破解攻击，给出防护建议"),
        ]
        for i, (label, text) in enumerate(scenarios):
            if scenario_cols[i].button(label, use_container_width=True, key=f"scenario_{i}"):
                st.session_state.auto_goal = text
                st.rerun()

        goal = st.text_area(
            "任务目标",
            value=st.session_state.get("auto_goal", ""),
            placeholder="例：帮我清理系统垃圾，删除大日志文件和临时文件，生成清理报告",
            height=72,
            key="auto_goal_input",
        )
        
        # A2赛题安全确认说明
        with st.expander("🔒 安全门控说明（A2赛题核心）"):
            st.markdown("""
            **规则门控分级**:
            - **自动放行**: ps/ss/df/grep等只读观测命令
            - **需确认**: kill/sudo/rm写操作等高危命令（须勾选下方确认框）
            - **拒绝**: rm -rf /、mkfs、关机重启等破坏性命令（永不执行）
            
            **最小权限执行**:
            - 当前非root用户时，高危操作会被拒绝或要求sudo
            - 自动创建的agent_ops受限账号用于执行隔离任务
            
            **链路溯源**:
            - 每步操作记录到data/audit.log
            - 完整TraceID贯穿「指令→感知→决策→校验→执行」
            """)
        
        allow_confirm = st.checkbox(
            "✅ 我确认允许执行高危终端命令（kill / sudo / rm写操作）",
            value=False,
            key="auto_confirm",
            help="A2赛题安全要求：高危操作必须用户显式确认"
        )

        col_a, col_b = st.columns(2)
        only_plan = col_a.checkbox("仅生成计划", value=False)
        if col_b.button("清空历史"):
            st.session_state.pop("last_auto_run", None)
            st.rerun()

        b1, b2 = st.columns(2)
        run_clicked = b1.button("▶ 启动自主任务", type="primary", use_container_width=True)
        resume_clicked = b2.button("继续执行（已确认）", use_container_width=True)

        if run_clicked and goal.strip():
            with st.spinner("执行中…"):
                if only_plan:
                    run = asyncio.run(agent.plan(goal.strip()))
                    st.session_state.last_auto_run = run
                else:
                    run = asyncio.run(
                        agent.run(goal.strip(), user_confirmed=st.session_state.get("auto_confirm", False))
                    )
                    st.session_state.last_auto_run = run
            st.session_state["_nav"] = "自主运维"
            st.rerun()

        if resume_clicked:
            last = st.session_state.get("last_auto_run")
            if last and last.state == WorkflowState.WAITING_CONFIRM:
                with st.spinner("继续…"):
                    run = asyncio.run(
                        agent.run(last.goal, user_confirmed=True, resume_run_id=last.run_id)
                    )
                    st.session_state.last_auto_run = run
                st.rerun()
            else:
                st.warning("无待确认任务")

    with tab_term:
        st.caption(
            f"白名单: ps / ss / df / grep / tail 等；写操作须勾选「自主任务」中的确认。"
            f" 命令执行时间显示为 {TZ_LABEL}。"
            " 若命令为 ps，其 START/TIME 列是进程启动/CPU 时间，不是本次执行时间。"
        )
        t1, t2 = st.columns([5, 1])
        with t1:
            cmd = st.text_input(
                "命令",
                value=st.session_state.get("term_cmd", "ps aux | head -10"),
                key="term_cmd_input",
                label_visibility="collapsed",
                placeholder="ps aux | head -10",
            )
        with t2:
            run_term = st.button("执行", key="term_run_btn", use_container_width=True)

        confirmed = st.session_state.get("auto_confirm", False)
        if run_term and cmd:
            check = check_terminal(cmd, user_confirmed=confirmed)
            st.caption(f"规则: {check.verdict.value} — {check.reason}")
            if check.verdict != RuleVerdict.DENY:
                with scroll_container(height=280):
                    r = run_terminal_sync(cmd, user_confirmed=confirmed)
                    st.code(r.to_text())
            st.session_state["term_cmd"] = cmd

    with tab_result:
        run = st.session_state.get("last_auto_run") or agent.last_run
        if not run:
            st.info("在「自主任务」页启动任务后，结果将显示在此")
            # A2赛题空状态引导
            st.markdown("""
            **预期执行链路（A2赛题5阶段）**:
            
            | 阶段 | 功能 | 技术实现 |
            |------|------|----------|
            | 1. 接收指令 | 自然语言理解 | LLM规划生成JSON步骤 |
            | 2. 感知环境 | OS状态采集 | tool/terminal调用df/ps/ss等 |
            | 3. 安全校验 | 指令风险评估 | rules.engine.check_terminal/tool |
            | 4. 受限执行 | 最小权限执行 | PrivilegeBroker降权执行 |
            | 5. 链路溯源 | 审计日志记录 | TraceContext + audit.log |
            """)
            return

        # A2赛题链路溯源展示
        st.caption(f"TraceID: `{run.run_id}` · 状态: {run.state.value} · 时间: {format_display(run.created_at)}")
        
        # 执行链路可视化
        if run.trace:
            with st.expander("🔍 执行链路溯源（A2赛题核心）", expanded=True):
                for i, trace_event in enumerate(run.trace[-20:], 1):  # 最近20条
                    event_type = trace_event.get("event", "unknown")
                    ts = trace_event.get("ts", "—")
                    
                    if event_type == "step_start":
                        step = trace_event.get("step", "?")
                        action = trace_event.get("action", "")[:40]
                        st.markdown(f"**{i}. 🚀 步骤启动** `{step}`: {action}")
                    elif event_type == "rule_deny":
                        reason = trace_event.get("reason", "")
                        st.error(f"**{i}. ⛔ 安全拦截**: {reason}")
                    elif event_type == "need_confirm":
                        step = trace_event.get("step", "?")
                        st.warning(f"**{i}. ⏸️ 等待确认**: 步骤 {step} 需用户确认后继续")
                    else:
                        st.text(f"{i}. {event_type}: {str(trace_event)[:60]}")

        if run.summary:
            st.success(safe_markdown(run.summary))
        if run.state == WorkflowState.WAITING_CONFIRM:
            st.warning("⏸️ 任务等待确认: 请回到「自主任务」页，勾选「允许高危命令」后点击「继续执行」")
            st.info("A2赛题安全设计: 高危操作必须用户显式确认后才继续")

        with scroll_container(height=520):
            steps_data = [
                {
                    "步骤": s.id,
                    "时间": format_display(s.started_at) if s.started_at else "—",
                    "类型": s.kind,
                    "动作": s.action[:50],
                    "状态": "✓ " + s.status if s.status == "done" else "⏸ " + s.status if s.status == "need_confirm" else s.status,
                    "输出": (s.output or s.error or "")[:80],
                }
                for s in run.steps
            ]
            if steps_data:
                st.dataframe(pd.DataFrame(steps_data), width="stretch", hide_index=True)
            with st.expander("原始输出（含安全校验详情）", expanded=False):
                for s in run.steps:
                    if s.output:
                        st.markdown(f"**{s.id}** `{s.action}`")
                        st.text((s.output or "")[:2000])
                        # A2赛题: 展示安全校验信息
                        if s.status == "failed" and s.error:
                            st.error(f"失败原因: {s.error}")
                        elif s.status == "need_confirm":
                            st.warning("该步骤需用户确认: 涉及高危操作（kill/sudo/rm）")

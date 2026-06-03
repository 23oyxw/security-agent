"""Streamlit — L2 Skill Flow 编排页（与 Vue /api/skills/flows 同源）."""

from __future__ import annotations

import asyncio
import json

import streamlit as st

from security_agent.agent.orchestrator import build_plan, build_skill_flow_context
from security_agent.skills.flows import list_flows, run_skill_flow


def page_skill_flows() -> None:
    st.markdown("### ⚙️ Skill 流程（L2）")
    st.caption(
        "确定性多步流程：逻辑在 `skills/flows/runner.py`，"
        "Streamlit / Vue / 智能助手经 orchestrator 或 REST 调用，主干只做拼接。"
    )

    flows = list_flows()
    if not flows:
        st.warning("未发现 L2 flow，请检查 security_agent/skills/flows/")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("已注册流程", len(flows))
    c2.metric("流程 ID", ", ".join(f["name"] for f in flows))
    c3.metric("说明", "REST: POST /api/skills/flows/{name}/run")

    st.divider()

    with st.expander("📋 流程清单", expanded=True):
        for f in flows:
            st.markdown(
                f"**{f.get('display_name', f['name'])}** (`{f['name']}`) · "
                f"{f.get('step_count', '?')} 步 — {f.get('description', '')}"
            )

    st.markdown("#### 运行流程")
    names = [f["name"] for f in flows]
    flow_name = st.selectbox("选择流程", names, format_func=lambda n: next(
        (x["display_name"] for x in flows if x["name"] == n), n
    ))

    user_message = st.text_area(
        "用户话术（用于 orchestrator 意图与上下文抽取）",
        value=_default_message(flow_name),
        height=80,
    )
    plan = build_plan(user_message)
    st.caption(f"detect_intent → `{plan.get('intent')}` · skill_flow → `{plan.get('skill_flow') or '—'}`")

    ctx = build_skill_flow_context(flow_name, user_message)
    if flow_name == "secure_exec":
        ctx["command"] = st.text_input("命令", value=ctx.get("command") or "ls -la /tmp")
        ctx["user_confirmed"] = st.checkbox("用户已确认", value=bool(ctx.get("user_confirmed")))
    elif flow_name == "alert_response":
        ctx["alert_event"] = {
            "message": st.text_input("告警内容", value="CPU 使用率持续高于 90%"),
            "source": "streamlit",
        }

    with st.expander("上下文 JSON", expanded=False):
        st.json(ctx)

    if st.button("▶ 执行 L2 Flow", type="primary", use_container_width=True):
        with st.spinner("执行中…"):
            result = asyncio.run(run_skill_flow(flow_name, ctx))
        st.session_state["_last_flow_result"] = result
        st.rerun()

    if "_last_flow_result" in st.session_state:
        result = st.session_state["_last_flow_result"]
        ok = result.get("ok")
        st.success("流程完成") if ok else st.error("流程未完全成功")
        st.markdown(f"**Trace ID:** `{result.get('trace_id', '—')}`")
        if result.get("report"):
            st.markdown("#### 扫描报告摘要")
            st.code((result["report"] or "")[:4000], language="text")
        if result.get("defense"):
            st.markdown("#### 三层防御")
            st.json(result["defense"])
        if result.get("execution"):
            st.markdown("#### 执行结果")
            st.json(result["execution"])
        if result.get("alert_responses"):
            st.markdown("#### Skill 响应")
            st.json(result["alert_responses"])
        with st.expander("完整 JSON"):
            st.json(result)


def _default_message(flow_name: str) -> str:
    defaults = {
        "scan_report": "生成扫描报告",
        "alert_response": "告警响应处理",
        "secure_exec": "安全执行 `ls -la /tmp`",
    }
    return defaults.get(flow_name, "")

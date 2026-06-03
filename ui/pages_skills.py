"""Skill 插件页面 — 支持独立 MCP 服务和本地 Skill 双模式."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from security_agent import config
from security_agent.skills.registry import list_skills, auto_discover, get_skill
from security_agent.tools.registry import call_tool_local

# ---- MCP 服务配置 ----
MCP_SERVICES = {
    "healthcheck": {
        "name": "健康巡检",
        "description": "CPU/内存/磁盘/网络监控，趋势分析",
        "port": 8081,
        "tools": 6,
    },
    "log_analyzer": {
        "name": "日志分析",
        "description": "多源日志采集、模式识别、异常检测",
        "port": 8082,
        "tools": 6,
    },
    "config_manager": {
        "name": "配置管理",
        "description": "配置文件快照、变更检测、版本追踪",
        "port": 8083,
        "tools": 5,
    },
    "security_hardening": {
        "name": "安全加固",
        "description": "SSH审计、防火墙审查、漏洞扫描",
        "port": 8084,
        "tools": 5,
    },
    "incident_responder": {
        "name": "故障响应",
        "description": "根因分析、自愈脚本、处置流程",
        "port": 8085,
        "tools": 4,
    },
}


def _ensure_discovered() -> None:
    """确保 Skill 已被自动发现并注册."""
    if not st.session_state.get("_skills_discovered"):
        auto_discover()
        st.session_state["_skills_discovered"] = True


def check_mcp_service_status(name: str, port: int) -> dict[str, Any]:
    """检查 MCP 服务状态（HTTP 模式）."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        
        if result == 0:
            # 端口开放，尝试获取信息
            import urllib.request
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/info",
                    method="GET",
                    headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    info = json.loads(resp.read().decode("utf-8"))
                    return {
                        "status": "running",
                        "mode": "http",
                        "info": info.get("info", {}),
                        "port": port,
                    }
            except Exception as e:
                return {
                    "status": "running",
                    "mode": "http",
                    "info": {"error": str(e)},
                    "port": port,
                }
        else:
            return {
                "status": "stopped",
                "mode": "http",
                "port": port,
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


def start_mcp_service(name: str, mode: str = "stdio") -> subprocess.Popen | None:
    """启动 MCP 服务."""
    try:
        cmd = [
            sys.executable,
            "-m",
            f"security_agent.skills.{name}.mcp_server",
        ]
        if mode == "http":
            cmd.extend(["--transport", "http"])
        
        # 后台启动
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(config.PROJECT_ROOT),
        )
        return proc
    except Exception as e:
        st.error(f"启动失败: {e}")
        return None


def call_mcp_tool_http(service: str, port: int, tool_name: str, args: dict) -> str:
    """通过 HTTP 调用 MCP 工具."""
    import urllib.request
    
    # MCP HTTP 调用需要特殊处理，这里用简单方式模拟
    # 实际应该使用 MCP 客户端库
    
    try:
        # 构造 JSON-RPC 请求
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args,
            }
        }).encode()
        
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/messages",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        return f"调用错误: {e}"


def call_mcp_tool_stdio(service: str, tool_name: str, args: dict) -> str:
    """通过 stdio 调用 MCP 工具（一次性调用）."""
    try:
        cmd = [
            sys.executable,
            "-m",
            f"security_agent.skills.{service}.mcp_server",
        ]
        
        # 构造 JSON-RPC 请求
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args,
            }
        }) + "\n"
        
        proc = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            cwd=str(config.PROJECT_ROOT),
            timeout=30,
        )
        
        if proc.returncode == 0:
            return proc.stdout
        else:
            return f"错误: {proc.stderr}"
    except subprocess.TimeoutExpired:
        return "调用超时 (30s)"
    except Exception as e:
        return f"调用错误: {e}"


async def run_mcp_tool(service: str, tool_name: str, args: dict, mode: str = "stdio") -> str:
    """异步运行 MCP 工具."""
    if mode == "http":
        port = MCP_SERVICES.get(service, {}).get("port", 0)
        return call_mcp_tool_http(service, port, tool_name, args)
    else:
        return call_mcp_tool_stdio(service, tool_name, args)


async def run_skill_tool(tool_name: str, args: dict) -> str:
    """异步运行本地 Skill 工具."""
    try:
        result = await call_tool_local(tool_name, args, user_confirmed=True)
        return result
    except Exception as e:
        return f"执行错误: {e}"


def page_skills() -> None:
    """Skill 插件管理页 — 支持独立 MCP 服务 + 本地 Skill."""
    _ensure_discovered()

    st.title("🧩 Skill 插件")
    st.caption("安全运维可插拔技能模块 — 支持独立 MCP 服务部署")

    # 模式选择
    mode_tabs = st.tabs(["🔌 MCP 独立服务", "🔧 本地 Skill", "⚙ L2 流程"])

    with mode_tabs[0]:
        _render_mcp_services_tab()

    with mode_tabs[1]:
        _render_local_skills_tab()

    with mode_tabs[2]:
        from ui.pages_skill_flows import page_skill_flows

        page_skill_flows()


def _render_mcp_services_tab() -> None:
    """渲染 MCP 独立服务标签页."""

    if st.button("🔄 热插拔重载（同步 Skill → MCP Host）", type="primary"):
        with st.spinner("重新发现 Skill 并刷新 MCP 注册表…"):
            try:
                from security_agent.mcp.registry import reload_mcp_plugins

                result = reload_mcp_plugins()
                st.success(
                    f"已重载 {result.get('servers_count', 0)} 个服务，"
                    f"{result.get('tools_count', 0)} 个工具"
                )
            except Exception as exc:
                st.error(f"重载失败: {exc}")
    
    with st.expander("📖 MCP 服务使用说明", expanded=False):
        st.markdown("""
        **什么是 MCP 独立服务？**
        - 每个 Skill 是一个独立的 MCP Server 进程
        - 可以单独启动、单独测试、独立部署
        - 支持 HTTP 模式（远程调用）和 stdio 模式（本地调用）
        
        **如何启动服务？**
        
        方式1 - 命令行启动：
        ```bash
        # 单个服务（HTTP 模式）
        uv run python -m security_agent.skills.launcher healthcheck --transport http
        
        # 所有服务（后台 HTTP 模式）
        uv run python -m security_agent.skills.launcher --all --transport http
        ```
        
        方式2 - 下方点击启动：
        - 在下方卡片中点击「启动服务」按钮
        
        **服务地址：**
        | 服务 | 地址 | 说明 |
        |------|------|------|
        | healthcheck | http://127.0.0.1:8081 | 健康巡检 |
        | log_analyzer | http://127.0.0.1:8082 | 日志分析 |
        | config_manager | http://127.0.0.1:8083 | 配置管理 |
        | security_hardening | http://127.0.0.1:8084 | 安全加固 |
        | incident_responder | http://127.0.0.1:8085 | 故障响应 |
        """)

    # 刷新状态按钮
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 刷新状态", use_container_width=True):
            st.rerun()
    with col2:
        st.caption("点击刷新查看服务最新状态")

    # 检查所有服务状态
    service_status = {}
    running_count = 0
    
    for name, cfg in MCP_SERVICES.items():
        status = check_mcp_service_status(name, cfg["port"])
        service_status[name] = status
        if status.get("status") == "running":
            running_count += 1

    # 状态统计
    c1, c2, c3 = st.columns(3)
    c1.metric("MCP 服务总数", len(MCP_SERVICES))
    c2.metric("运行中", running_count)
    c3.metric("已停止", len(MCP_SERVICES) - running_count)
    
    st.divider()

    # 批量操作
    if running_count < len(MCP_SERVICES):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ 一键启动所有服务（HTTP）", use_container_width=True):
                with st.spinner("正在启动所有服务..."):
                    for name in MCP_SERVICES:
                        if service_status[name].get("status") != "running":
                            proc = start_mcp_service(name, mode="http")
                            if proc:
                                st.session_state[f"mcp_proc_{name}"] = proc
                st.success("启动命令已发送，请刷新查看状态")
                st.rerun()

    # 渲染每个服务卡片
    for name, cfg in MCP_SERVICES.items():
        status = service_status.get(name, {})
        is_running = status.get("status") == "running"
        
        with st.container(border=True):
            # 头部信息
            hdr1, hdr2, hdr3 = st.columns([3, 1, 1])
            
            with hdr1:
                status_icon = "🟢" if is_running else "⚫"
                st.markdown(f"### {status_icon} {cfg['name']}")
                st.caption(f"`{name}` · 端口 {cfg['port']} · {cfg['tools']} 个工具")
                st.markdown(cfg["description"])
            
            with hdr2:
                if is_running:
                    st.success("运行中")
                    st.caption(f"模式: {status.get('mode', 'http')}")
                else:
                    st.error("已停止")
            
            with hdr3:
                if not is_running:
                    if st.button("▶️ 启动", key=f"start_{name}", use_container_width=True):
                        with st.spinner(f"启动 {name}..."):
                            proc = start_mcp_service(name, mode="http")
                            if proc:
                                st.session_state[f"mcp_proc_{name}"] = proc
                                st.success(f"{name} 已启动")
                                st.rerun()
                else:
                    # 服务运行中，显示工具调用区
                    pass
            
            # 运行中的服务显示工具
            if is_running:
                st.divider()
                
                # 获取工具列表
                info = status.get("info", {})
                tools = info.get("tools", [])
                
                if tools:
                    st.markdown(f"**可用工具 ({len(tools)})**")
                    
                    # 为每个工具创建调用区
                    for i, tool in enumerate(tools):
                        tool_col1, tool_col2 = st.columns([4, 1])
                        
                        with tool_col1:
                            st.markdown(f"**`{tool['name']}`** — {tool.get('description', '')}")
                            
                            # 显示参数
                            params = tool.get("parameters", {}).get("properties", {})
                            if params:
                                with st.expander("参数说明"):
                                    for pname, pinfo in params.items():
                                        req = "必填" if pname in tool.get("parameters", {}).get("required", []) else "可选"
                                        st.caption(f"- `{pname}` ({pinfo.get('type', 'any')}, {req}): {pinfo.get('description', '无说明')}")
                            
                            # 是否需要确认
                            if tool.get("requires_confirmation"):
                                st.caption("🔒 **此工具需要用户确认**")
                        
                        with tool_col2:
                            params = tool.get("parameters", {}).get("properties", {})
                            if not params:
                                # 无参数工具直接运行
                                if st.button("运行", key=f"mcp_run_{name}_{tool['name']}_{i}", use_container_width=True):
                                    with st.spinner("执行中..."):
                                        result = asyncio.run(run_mcp_tool(name, tool["name"], {}, mode="http"))
                                    st.session_state[f"mcp_result_{name}_{tool['name']}"] = result
                            else:
                                # 有参数工具显示参数输入
                                if st.button("配置运行", key=f"mcp_cfg_{name}_{tool['name']}_{i}", use_container_width=True):
                                    st.session_state[f"mcp_show_args_{name}_{tool['name']}"] = True
                        
                        # 参数输入区
                        if st.session_state.get(f"mcp_show_args_{name}_{tool['name']}", False):
                            args = {}
                            required = tool.get("parameters", {}).get("required", [])
                            for pname, pinfo in params.items():
                                label = f"{pname} {'*' if pname in required else ''}"
                                key = f"mcp_arg_{name}_{tool['name']}_{pname}"
                                
                                if pinfo.get("type") == "integer":
                                    default = pinfo.get("default", 0)
                                    args[pname] = st.number_input(label, key=key, value=int(default), step=1)
                                elif pinfo.get("type") == "boolean":
                                    default = pinfo.get("default", False)
                                    args[pname] = st.checkbox(label, key=key, value=default)
                                else:
                                    default = pinfo.get("default", "")
                                    args[pname] = st.text_input(label, key=key, value=str(default))
                            
                            # 确认按钮
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                if st.button("确认运行", key=f"mcp_exec_{name}_{tool['name']}"):
                                    with st.spinner("执行中..."):
                                        result = asyncio.run(run_mcp_tool(name, tool["name"], args, mode="http"))
                                    st.session_state[f"mcp_result_{name}_{tool['name']}"] = result
                                    st.session_state[f"mcp_show_args_{name}_{tool['name']}"] = False
                                    st.rerun()
                        
                        # 显示执行结果
                        result_key = f"mcp_result_{name}_{tool['name']}"
                        if result_key in st.session_state:
                            with st.container():
                                st.caption("执行结果:")
                                result_data = st.session_state[result_key]
                                try:
                                    # 尝试解析 JSON
                                    if isinstance(result_data, str):
                                        data = json.loads(result_data)
                                        st.json(data)
                                    else:
                                        st.json(result_data)
                                except json.JSONDecodeError:
                                    st.code(str(result_data), language="text")
                        
                        st.divider()
                else:
                    st.info("服务运行中，但无法获取工具列表。可能服务尚未完全初始化，请刷新。")


def _render_local_skills_tab() -> None:
    """渲染本地 Skill 标签页（保持原有功能）."""
    
    with st.expander("📖 本地 Skill 使用说明", expanded=False):
        st.markdown("""
        **本地 Skill 是什么？**
        - Skill 是可插拔的安全运维模块，运行在 Agent 进程中
        - 每个 Skill 包含多个专用工具，通过 Tool Registry 注册
        
        **注意：** 建议优先使用 MCP 独立服务模式，本地模式将逐步迁移。
        """)

    skills = list_skills()

    if not skills:
        st.warning("未发现已注册的 Skill。请确认 security_agent/skills/ 下的模块是否完整。")
        return

    # 统计卡片
    c1, c2, c3 = st.columns(3)
    c1.metric("已注册插件", len(skills))
    c2.metric("工具总数", sum(s.get("tool_count", 0) for s in skills))
    c3.metric("需 Root", sum(1 for s in skills if s.get("requires_root")))

    st.divider()

    # 每个 Skill 一张卡片
    for sk in skills:
        with st.container(border=True):
            hdr1, hdr2 = st.columns([3, 1])
            with hdr1:
                name = sk.get("display_name") or sk.get("name", "")
                tags = ", ".join(sk.get("tags", []))
                st.markdown(f"### 🔧 {name}")
                st.caption(f"`{sk.get('name', '')}` · v{sk.get('version', '?')} · 工具 {sk.get('tool_count', 0)} 个")
                if tags:
                    st.caption(f"标签: {tags}")
                if sk.get("description"):
                    st.markdown(sk["description"])
            with hdr2:
                if sk.get("requires_root"):
                    st.warning("🔒 需 Root")
                else:
                    st.success("✅ 无需 Root")

            # 展开详情：工具列表 + 运行按钮
            skill_obj = get_skill(sk["name"])
            if skill_obj:
                with st.expander("🚀 展开工具列表（可运行）", expanded=False):
                    tools = skill_obj.get_tools()
                    playbooks = skill_obj.get_playbooks()
                    rules = skill_obj.get_rules()

                    st.markdown(f"**可用工具 ({len(tools)})**")
                    
                    # 为每个工具创建运行区
                    for i, t in enumerate(tools):
                        tool_col1, tool_col2 = st.columns([4, 1])
                        
                        with tool_col1:
                            st.markdown(f"**`{t.name}`** — {t.description}")
                            # 显示参数
                            params = t.parameters.get("properties", {})
                            if params:
                                with st.expander("参数说明"):
                                    for pname, pinfo in params.items():
                                        req = "必填" if pname in t.parameters.get("required", []) else "可选"
                                        st.caption(f"- `{pname}` ({pinfo.get('type', 'any')}, {req}): {pinfo.get('description', '无说明')}")
                        
                        with tool_col2:
                            # 根据是否有参数决定是否显示输入框
                            params = t.parameters.get("properties", {})
                            if not params:
                                # 无参数工具直接运行
                                if st.button("运行", key=f"run_{sk['name']}_{t.name}_{i}", use_container_width=True):
                                    with st.spinner("执行中..."):
                                        result = asyncio.run(run_skill_tool(t.name, {}))
                                    st.session_state[f"result_{t.name}"] = result
                            else:
                                # 有参数工具显示参数输入
                                if st.button("配置运行", key=f"cfg_{sk['name']}_{t.name}_{i}", use_container_width=True):
                                    st.session_state[f"show_args_{t.name}"] = True
                        
                        # 参数输入区
                        if st.session_state.get(f"show_args_{t.name}", False):
                            args = {}
                            required = t.parameters.get("required", [])
                            for pname, pinfo in params.items():
                                label = f"{pname} {'*' if pname in required else ''}"
                                if pinfo.get("type") == "integer":
                                    args[pname] = st.number_input(label, key=f"arg_{t.name}_{pname}", value=0, step=1)
                                elif pinfo.get("type") == "boolean":
                                    args[pname] = st.checkbox(label, key=f"arg_{t.name}_{pname}")
                                else:
                                    args[pname] = st.text_input(label, key=f"arg_{t.name}_{pname}", value=pinfo.get("default", ""))
                            
                            if st.button("确认运行", key=f"exec_{t.name}"):
                                with st.spinner("执行中..."):
                                    result = asyncio.run(run_skill_tool(t.name, args))
                                st.session_state[f"result_{t.name}"] = result
                                st.session_state[f"show_args_{t.name}"] = False
                                st.rerun()
                        
                        # 显示执行结果
                        result_key = f"result_{t.name}"
                        if result_key in st.session_state:
                            with st.container():
                                st.caption("执行结果:")
                                try:
                                    # 尝试格式化 JSON
                                    data = json.loads(st.session_state[result_key])
                                    st.json(data)
                                except json.JSONDecodeError:
                                    st.code(st.session_state[result_key], language="text")
                        
                        st.divider()

                    # 关联知识库
                    if playbooks:
                        st.markdown(f"**📚 关联知识库 ({len(playbooks)})**")
                        for pb in playbooks:
                            st.markdown(f"- **{pb.title}** (`{pb.id}`) · 严重度: {pb.severity}")

                    # 运维规则
                    if rules:
                        st.markdown(f"**📋 运维规则 ({len(rules)})**")
                        for r in rules:
                            st.caption(f"• {r}")

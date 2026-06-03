"""Agent decision layer — 编排 + 多轮工具调用."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol

from openai import OpenAI

from security_agent import config
from security_agent.agent.fallback import FallbackClient
from security_agent.agent.orchestrator import (
    build_plan,
    build_skill_flow_context,
    format_plan_for_llm,
)
from security_agent.agent.advisor import build_structured_advice, format_advice_for_user
from security_agent.agent.policy import should_auto_warn, summarize_risks
from security_agent.agent.rules import build_system_prompt_extension
from security_agent.agent.react_context import (
    apply_history_budget,
    build_react_user_message,
    truncate_observation,
)
from security_agent.retrieval.hybrid import format_grounding_block, search_knowledge
from security_agent.tools.registry import call_tool_local, list_tool_schemas_openai
from security_agent.audit.spine import IncidentSpine, incident_spine
from security_agent.resilience.budget import BudgetExpiredError
from security_agent.resilience.degradation import DegradationLevel, try_rule_fallback
from security_agent.agent.perception import get_system_context
from security_agent.memory import get_conversation_memory
from security_agent.utils import get_token_manager
from security_agent.safety_gate import SafetyGate

SYSTEM_PROMPT = (
    """你是「安全运维智能助手」，擅长主机安全运维与工具编排。

【领域边界 — 只处理以下安全运维问题】
✅ 属于你的职责：安全扫描、高危进程排查与拦截、端口暴露检测、登录审计、日志异常分析、安全加固建议、敏感文件监控、漏洞排查、安全报告生成、开发环境安全配置检查（如 .env 泄露、API Key 暴露、依赖漏洞、敏感文件权限）、配置文件变更审计。
✅ 灰色地带（可以回答安全相关部分）：项目开发过程中的安全风险管控——只能回答与安全相关的部分（如密钥管理、依赖漏洞、配置泄露、代码仓库安全），不能回答项目管理风险（如进度延期、需求变更、资源不足、人员分配）。
❌ 不属于你的职责：CPU 超频/加速、硬件升级推荐、应用性能调优、项目管理（进度/需求/人员）、编程教学、闲聊、写代码。对于超出安全运维范围的问题，简短说明"我专注于安全运维，这个问题超出我的能力范围"并建议用户咨询对应工具或专家。

能力：安全扫描、进程分析、拦截（需确认）、HTML 报告、监控启停、审计、终端命令（白名单）、自主任务 run_autonomous_mission。

**OS 环境深度感知能力（赛题核心）：**
你可以调用底层系统工具获取实时 OS 上下文，包括：
- ps aux（进程快照）/ lsof（打开文件/连接）/ ss/netstat（网络连接状态）
- journalctl（系统日志按优先级过滤）/ syslog（日志关键字检索）
- df -h（磁盘使用率）/ find（大文件扫描）
- /proc/loadavg + free -h（系统负载+内存）
- 僵尸进程检测、OOM 事件检测

**智能根因分析：**
当用户报告系统异常或你观察到异常指标时，应主动运行根因分析（root_cause_analyzer），
输出：分类、严重度、证据链、根因描述、处置建议、置信度。
分析维度：磁盘满→日志堆积/僵尸进程→PID耗尽/OOM→内存不足/高负载→CPU密集型进程/异常端口→未授权服务。

风格：像资深 SRE — 先给结论，再给依据；不确定时先调工具再回答；可连续多工具完成任务。回复要精炼：直接回答用户问题，不主动添加用户没问的内容（如方法论、建议），除非用户明确要求。结论前置，数据用表格，避免长段文字。

面向非专业用户：回复中提到任何进程名或 PID 时，必须附带一句话说明该进程是什么软件/功能（如 PID 18871 (/opt/QQ/qq) 即时通讯软件 QQ），让没有运维背景的人也能理解。不要假设用户知道每个进程的用途。
工具返回大量进程数据时，只在回复中列出与安全相关或用户明确关心的进程（最多 10 个），内核线程（kworker、ksoftirqd、migration 等）和系统守护进程（systemd、journald 等）一句话概括即可，逐条列出。
防幻觉：回答安全建议前优先 search_security_knowledge；必须引用知识库编号（PB-*）或工具输出，禁止编造 PID/端口/扫描结果。
涉及 root 写操作、杀进程、改权限：明确提示须用户在界面勾选确认。
禁止在回复正文中输出 DSML、XML、invoke、tool_calls 等工具调用标记；需要工具时必须走 API tools 通道，正文只写用户能读懂的中文结论。
用户简短确认（如「需要」「好的」）时，结合上一轮对话执行已建议的处置，勿重新跑全量加固/日志扫描。
"""
    + build_system_prompt_extension()
)


class ToolExecutor(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> str: ...


class LocalToolExecutor:
    def __init__(self, *, user_confirmed: bool = False):
        self.user_confirmed = user_confirmed

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> str:
        return await call_tool_local(name, arguments, user_confirmed=self.user_confirmed)


# 对话记忆轮数见 config.MAX_HISTORY_ROUNDS


class AgentBrain:
    def __init__(
        self,
        executor: ToolExecutor | None = None,
        max_tool_rounds: int | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        session_id: str | None = None,
        user_confirmed: bool = False,
    ):
        _key = api_key or config.LLM_API_KEY
        if not _key:
            raise ValueError("未配置 LLM API Key，请在 .env 设置 LLM_API_KEY 或 DEEPSEEK_API_KEY")
        self.client = OpenAI(
            api_key=_key,
            base_url=base_url or config.LLM_BASE_URL,
        )
        self.model = config.resolve_agent_model(model)
        self.user_confirmed = user_confirmed
        self.executor = executor or LocalToolExecutor(user_confirmed=user_confirmed)
        self.max_tool_rounds = max_tool_rounds if max_tool_rounds is not None else config.REACT_MAX_TOOL_ROUNDS
        self.tools = list_tool_schemas_openai()
        self._history: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # 持久化记忆
        self.memory = get_conversation_memory()
        self.token_manager = get_token_manager()
        self.safety_gate = SafetyGate()
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d')}"
        
        # 从数据库加载历史
        self._load_history_from_db()

        # Fallback 客户端（自动回退机制）
        self._fallback_client = FallbackClient(
            primary_client=self.client,
            primary_model=self.model,
        )

    def reset(self) -> None:
        self._history = [{"role": "system", "content": SYSTEM_PROMPT}]
        try:
            self.memory.clear_conversation(self.session_id)
        except Exception:
            pass

    def get_fallback_stats(self) -> dict[str, Any]:
        """获取 fallback 统计信息."""
        return self._fallback_client.get_stats()

    def _load_history_from_db(self) -> None:
        """从数据库加载历史记录"""
        try:
            db_messages = self.memory.get_history_for_llm(
                self.session_id, max_rounds=config.MAX_HISTORY_ROUNDS,
            )
            if db_messages:
                has_system = any(m.get("role") == "system" for m in db_messages)
                if has_system:
                    self._history = db_messages
                else:
                    self._history = [{"role": "system", "content": SYSTEM_PROMPT}, *db_messages]
            else:
                self._history = [{"role": "system", "content": SYSTEM_PROMPT}]
        except Exception:
            self._history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    def _save_message_to_db(self, role: str, content: str, metadata: dict = None) -> None:
        """保存消息到数据库"""
        try:
            self.memory.add_message(self.session_id, role, content, metadata)
        except Exception as e:
            print(f"保存消息到数据库失败: {e}")
    
    def _trim_history(self) -> None:
        """跨轮对话：截断 tool 观测 + 条数窗口 + token 压缩."""
        self._history = apply_history_budget(self._history, self.token_manager)

    def _apply_react_context_budget(self) -> None:
        """ReAct 每轮工具调用后调用，防止单轮内上下文膨胀."""
        self._history = apply_history_budget(self._history, self.token_manager)

    @staticmethod
    def _merge_openai_usage(acc: dict[str, Any], response: Any) -> bool:
        """累加多轮 LLM 调用的 token（ReAct 每轮都会计费）."""
        usage = getattr(response, "usage", None)
        if not usage:
            return False
        p = int(usage.prompt_tokens or 0)
        c = int(usage.completion_tokens or 0)
        t = int(usage.total_tokens or 0) or (p + c)
        if not (p or c or t):
            return False
        acc["prompt_tokens"] = acc.get("prompt_tokens", 0) + p
        acc["completion_tokens"] = acc.get("completion_tokens", 0) + c
        acc["total_tokens"] = acc.get("total_tokens", 0) + t
        return True

    def _note_llm_call(self, spine: IncidentSpine, token_usage: dict[str, Any], response: Any) -> None:
        spine.reasoning.llm_calls_count += 1
        self._merge_openai_usage(token_usage, response)

    async def _run_skill_flow_plan(
        self,
        flow_name: str,
        user_message: str,
        spine: IncidentSpine,
        tool_trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """执行 L2 Skill Flow 并格式化为对话回复."""
        from security_agent.skills.flows import run_skill_flow

        ctx = build_skill_flow_context(flow_name, user_message)
        ctx["trace_id"] = spine.trace_id
        spine.stage("skill_flow_start", {"flow": flow_name, "context_keys": list(ctx.keys())})
        if flow_name == "secure_exec" and not ctx.get("command"):
            reply = (
                "【安全命令执行】请用反引号标出待执行命令，例如：\n"
                "安全执行 `ls -la /var/log`\n"
                "高危命令请同时说明「已确认」。"
            )
            self._history.append({"role": "user", "content": user_message})
            self._history.append({"role": "assistant", "content": reply})
            return self._enrich_response(
                {
                    "reply": reply,
                    "tool_trace": tool_trace,
                    "plan": {"intent": "secure_exec_flow", "skill_flow": flow_name},
                    "skill_flow": flow_name,
                    "token_usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                    "model_used": "",
                },
                spine,
            )

        result = await run_skill_flow(flow_name, ctx, trace_id=spine.trace_id)
        tool_trace.append({"skill_flow": flow_name, "result": result})
        from security_agent.agent.skill_flow_format import format_skill_flow_reply

        reply = format_skill_flow_reply(flow_name, result)
        end_detail: dict[str, Any] = {
            "flow": flow_name,
            "ok": result.get("ok"),
            "trace_id": spine.trace_id,
        }
        if flow_name == "alert_response":
            end_detail["alert_responses"] = result.get("alert_responses") or []
            if result.get("alert_event"):
                end_detail["alert_event"] = result["alert_event"]
            end_detail["steps"] = result.get("steps") or []
        if flow_name == "secure_exec":
            defense = result.get("defense") or {}
            wrap = result.get("execution") or {}
            if not defense and isinstance(wrap.get("defense_result"), dict):
                defense = wrap["defense_result"]
            exec_res = wrap.get("execution_result") if isinstance(wrap.get("execution_result"), dict) else {}
            end_detail["command"] = result.get("command") or defense.get("target") or ""
            end_detail["verdict"] = defense.get("overall_verdict", "")
            end_detail["score"] = defense.get("overall_score")
            end_detail["exit_code"] = exec_res.get("exit_code")
            end_detail["exec_ok"] = exec_res.get("ok")
        elif flow_name == "scan_report":
            scan = result.get("scan") or {}
            exp = scan.get("exposed_ports") or result.get("exposed_ports") or {}
            risky = exp.get("risky_count") if isinstance(exp, dict) else None
            if risky is None:
                for st in result.get("steps") or []:
                    if st.get("step") == "exposed_ports" and st.get("risky_count") is not None:
                        risky = st["risky_count"]
                        break
            end_detail["risk_count"] = scan.get("risk_count")
            if end_detail["risk_count"] is None:
                end_detail["risk_count"] = len(scan.get("risks") or [])
            end_detail["risky_ports"] = risky if risky is not None else 0
            end_detail["report_len"] = len(result.get("report") or "")
            end_detail["report_html_path"] = result.get("report_html_path") or ""
            end_detail["steps"] = result.get("steps") or []
            if scan:
                end_detail["scan"] = scan
        spine.stage("skill_flow_end", end_detail)
        if flow_name == "secure_exec":
            wrap = result.get("execution") or {}
            exec_res = wrap.get("execution_result") if isinstance(wrap.get("execution_result"), dict) else wrap
            spine.post_verify(
                {
                    "ok": result.get("ok") and exec_res.get("ok", True),
                    "exit_code": exec_res.get("exit_code"),
                    "message": (exec_res.get("stdout") or "")[:200],
                },
            )
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": reply})
        return self._enrich_response(
            {
                "reply": reply,
                "tool_trace": tool_trace,
                "plan": {"intent": flow_name, "skill_flow": flow_name},
                "skill_flow": flow_name,
                "auto_warn": not result.get("ok"),
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
                "model_used": "",
            },
            spine,
        )

    async def _run_planned_chain(
        self,
        chain: list[str],
        *,
        user_message: str = "",
        tool_args: dict[str, dict[str, Any]] | None = None,
        use_parallel: bool = True,
    ) -> tuple[str, list[dict[str, Any]]]:
        """执行工具链，支持串行或并行模式.

        Args:
            chain: 工具名称列表
            use_parallel: 是否尝试并行执行独立的只读工具

        Returns:
            (汇总结果, 执行追踪)
        """
        from security_agent.agent.orchestrator import build_tool_args
        from security_agent.agent.parallel import is_tool_parallel_safe, run_tools_parallel

        def _args_for(name: str) -> dict[str, Any]:
            if tool_args and name in tool_args:
                return dict(tool_args[name])
            return build_tool_args(name, user_message)

        trace: list[dict[str, Any]] = []

        # 判断是否可以使用并行：所有工具都是只读安全的
        can_parallel = use_parallel and all(is_tool_parallel_safe(name) for name in chain)

        if can_parallel and len(chain) > 1:
            # 并行执行模式
            tool_calls: list[tuple[str, dict[str, Any]]] = []
            for name in chain:
                tool_calls.append((name, _args_for(name)))

            parallel_result = await run_tools_parallel(tool_calls, max_concurrency=len(chain))

            # 构建 trace 和 parts
            parts: list[str] = []
            for name in chain:
                if name in parallel_result.get("results", {}):
                    out = parallel_result["results"][name]
                    trace.append({
                        "tool": name,
                        "args": _args_for(name),
                        "output": out[:2000],
                        "parallel": True,
                        "duration_ms": parallel_result.get("timing", {}).get(name, 0),
                    })
                    parts.append(f"### {name}\n{out[:1500]}")
                elif name in parallel_result.get("errors", {}):
                    err = parallel_result["errors"][name]
                    trace.append({
                        "tool": name,
                        "args": _args_for(name),
                        "error": err,
                        "parallel": True,
                    })
                    parts.append(f"### {name}\n[错误] {err}")

            summary = "\n\n".join(parts)
            return summary, trace

        # 串行执行模式（默认）
        parts = []
        for name in chain:
            args = _args_for(name)
            out = await self.executor.call_tool(name, args)
            trace.append({"tool": name, "args": args, "output": out[:2000], "parallel": False})
            parts.append(f"### {name}\n{out[:1500]}")
        summary = "\n\n".join(parts)
        return summary, trace

    def _enrich_response(self, resp: dict[str, Any], spine: IncidentSpine) -> dict[str, Any]:
        tu = resp.get("token_usage") or {}
        total = int(tu.get("total_tokens") or 0)
        if total:
            spine.reasoning.total_tokens_used = total
            model = resp.get("model_used") or self.model
            try:
                from security_agent.agent.cost import get_global_tracker

                get_global_tracker().add_from_usage(model, tu)
            except Exception:
                pass
        resp["trace_id"] = spine.trace_id
        resp.setdefault("degradation_level", spine.degradation_level)
        try:
            from security_agent.agent.cost import attach_usage_meta

            attach_usage_meta(resp, self._history, token_manager=self.token_manager)
        except Exception:
            pass
        return resp

    async def _degraded_or_error(
        self,
        spine: IncidentSpine,
        user_message: str,
        plan: dict[str, Any],
        tool_trace: list[dict[str, Any]],
        token_usage: dict[str, Any],
        err: Exception | str,
        *,
        fallback_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = fallback_metadata or {}
        spine.stage("inference_decision", {"error": str(err)[:400], "llm": meta})
        degraded = await try_rule_fallback(
            user_message, plan=plan, trace_id=spine.trace_id,
        )
        if degraded:
            spine.set_degradation(DegradationLevel.S2_RULE, str(err)[:200])
            degraded["tool_trace"] = tool_trace + degraded.get("tool_trace", [])
            degraded["token_usage"] = token_usage
            return self._enrich_response(degraded, spine)
        return self._enrich_response(
            {
                "reply": f"模型调用失败: {err}",
                "tool_trace": tool_trace,
                "plan": plan,
                "auto_warn": False,
                "citations": [],
                "token_usage": token_usage,
                "model_used": self.model,
                "fallback_used": meta.get("fallback_used", False),
                "error": str(err),
            },
            spine,
        )

    def _grounding_prefix(self, user_message: str) -> str:
        hits = search_knowledge(user_message, top_k=5)
        return format_grounding_block(hits)

    @staticmethod
    def _finalize_llm_text(raw: str, user_message: str) -> str:
        from security_agent.agent.reply_sanitize import (
            fallback_reply_when_markup_only,
            is_markup_heavy,
            sanitize_assistant_reply,
        )

        text = sanitize_assistant_reply(raw or "")
        if is_markup_heavy(text):
            return fallback_reply_when_markup_only(user_message)
        return text

    async def chat(self, user_message: str) -> dict[str, Any]:
        from security_agent.agent.parallel import run_security_info_gathering

        with incident_spine(
            user_message,
            session_id=getattr(self, "session_id", ""),
            budget_sec=config.REQUEST_BUDGET_SEC,
        ) as spine:
            return await self._chat_inner(user_message, spine, run_security_info_gathering)

    async def _chat_inner(
        self,
        user_message: str,
        spine: IncidentSpine,
        run_security_info_gathering,
    ) -> dict[str, Any]:
        spine.stage("receive_request", {"user_message": user_message[:500]})
        self._trim_history()
        
        # 注入环境感知上下文
        system_ctx = get_system_context()
        
        # Token统计
        if hasattr(self, 'token_manager'):
            stats = self.token_manager.analyze_context(self._history)
            if stats.is_over_limit:
                self._trim_history()  # 自动压缩
        plan = build_plan(user_message, self._history)
        effective_message = plan.get("user_message_resolved") or user_message
        tool_trace: list[dict[str, Any]] = [{"plan": plan}]
        grounding = self._grounding_prefix(user_message)

        # Token 使用追踪
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # L2 Skill Flow：主干只拼接，流程逻辑在 skills/flows
        if plan.get("skill_flow"):
            return await self._run_skill_flow_plan(
                plan["skill_flow"], effective_message, spine, tool_trace,
            )

        # 并行信息采集意图：使用并行执行器同时采集多个独立信息
        if plan["intent"] == "parallel_info":
            # 阶段2: 感知环境
            spine.stage("environment_probe", {
                "intent": "parallel_info",
                "parallel_execution": True,
                "system_context": system_ctx[:500],
            })
            parallel_result = await run_security_info_gathering(
                include_scan=True,
                include_processes=True,
                include_health=True,
                include_network=False,  # 减少并行压力
                include_ports=True,
            )

            # 构建工具输出
            tool_out_parts = [parallel_result.get("summary", "")]
            tool_out_parts.append(f"\n并行执行耗时: {parallel_result.get('total_time_ms', 0)}ms")
            tool_out_parts.append(f"成功: {parallel_result.get('successful', 0)}/{parallel_result.get('total', 0)}")

            for tool_name, result in parallel_result.get("results", {}).items():
                tool_out_parts.append(f"\n### {tool_name}\n{result[:1500]}")

            tool_out = "\n\n".join(tool_out_parts)
            
            # 记录环境感知结果
            spine.stage("environment_probe_result", {
                "total_time_ms": parallel_result.get("total_time_ms", 0),
                "successful": parallel_result.get("successful", 0),
                "total": parallel_result.get("total", 0),
            })
            tool_trace.append({"parallel_execution": parallel_result})

            self._history.append({"role": "user", "content": user_message})
            # 保存到数据库
            if len(self._history) > 0:
                last_msg = self._history[-1]
                self._save_message_to_db(last_msg.get("role", ""), last_msg.get("content", ""), {"source": "chat"})
            risks = _extract_risks_from_tool_output(tool_out)
            advice = build_structured_advice(user_message, risks=risks, tool_summary=tool_out[:3000])
            self._history.append(
                {
                    "role": "user",
                    "content": (
                        f"{advice['grounding_text']}\n"
                        f"当前系统环境：\n{system_ctx}\n\n"
                        f"已并行完成系统信息采集，结果如下。请总结关键发现：\n\n"
                        f"{tool_out[:config.REACT_CHAIN_OUTPUT_MAX_CHARS]}\n\n"
                        f"参考骨架：\n{format_advice_for_user(advice)}"
                    ),
                }
            )
            try:
                response, fallback_metadata = self._fallback_client.chat_completion(
                    messages=self._history,
                )
            except Exception as e:
                return await self._degraded_or_error(
                    spine, user_message, plan, tool_trace, token_usage, e,
                )
            text = self._finalize_llm_text(response.choices[0].message.content or "", user_message)
            self._note_llm_call(spine, token_usage, response)
            self._history.append({"role": "assistant", "content": text})

            spine.stage("inference_decision", {
                "advice_type": advice.get("type", "unknown"),
                "risk_count": len(risks),
                "tool_summary_length": len(tool_out),
            })
            
            # 阶段4: 安全校验（LLM决策本身）
            spine.stage("safety_check", {
                "model": fallback_metadata.get("fallback_model") if fallback_metadata.get("fallback_used") else self.model,
                "fallback_used": fallback_metadata.get("fallback_used", False),
                "response_length": len(text),
            })
            
            # 阶段5: 执行结果
            spine.record_llm_meta(fallback_metadata)
            spine.stage("execution", {
                "reply_length": len(text),
                "token_usage": token_usage,
                "tool_trace_count": len(tool_trace),
            })
            spine.post_verify({"ok": True, "message": "parallel_info summary"})
            return self._enrich_response(
                {
                    "reply": text,
                    "tool_trace": tool_trace,
                    "plan": plan,
                    "auto_warn": self._maybe_warn_from_trace(tool_trace),
                    "advice": advice,
                    "citations": advice.get("citations", []),
                    "parallel": True,
                    "token_usage": token_usage,
                    "model_used": fallback_metadata.get("fallback_model")
                    if fallback_metadata.get("fallback_used")
                    else self.model,
                    "fallback_used": fallback_metadata.get("fallback_used", False),
                    "fallback_metadata": fallback_metadata,
                },
                spine,
            )

        # 快捷编排：明确意图且有关键词链时，先执行工具再把结果交给 LLM 总结
        if plan["tool_chain"] and plan["intent"] != "block":
            # 对独立的只读工具链使用并行执行
            # 阶段2: 感知环境（工具执行）
            spine.stage("environment_probe", {
                "intent": plan["intent"],
                "tool_chain": plan["tool_chain"],
                "parallel_execution": len(plan["tool_chain"]) > 1,
            })
            use_parallel = len(plan["tool_chain"]) > 1
            tool_out, chain_trace = await self._run_planned_chain(
                plan["tool_chain"],
                user_message=effective_message,
                tool_args=plan.get("tool_args"),
                use_parallel=use_parallel,
            )
            
            # 记录工具执行结果
            spine.stage("environment_probe_result", {
                "tool_chain_executed": len(chain_trace),
                "tool_output_length": len(tool_out),
                "parallel_used": use_parallel,
            })
            tool_trace.extend(chain_trace)
            self._history.append({"role": "user", "content": user_message})
            # 保存到数据库
            if len(self._history) > 0:
                last_msg = self._history[-1]
                self._save_message_to_db(last_msg.get("role", ""), last_msg.get("content", ""), {"source": "chat"})
            risks = _extract_risks_from_tool_output(tool_out)
            advice = build_structured_advice(user_message, risks=risks, tool_summary=tool_out[:3000])
            self._history.append(
                {
                    "role": "user",
                    "content": (
                        f"{advice['grounding_text']}\n"
                        f"工具已执行完毕，结果如下。请按结构化建议回复（结论/步骤/请勿），"
                        f"并引用知识库编号：\n\n{tool_out[:config.REACT_CHAIN_OUTPUT_MAX_CHARS]}\n\n"
                        f"参考骨架：\n{format_advice_for_user(advice)}"
                    ),
                }
            )
            try:
                response, fallback_metadata = self._fallback_client.chat_completion(
                    messages=self._history,
                )
            except Exception as e:
                return await self._degraded_or_error(
                    spine, user_message, plan, tool_trace, token_usage, e,
                )
            text = self._finalize_llm_text(response.choices[0].message.content or "", user_message)
            self._note_llm_call(spine, token_usage, response)
            self._history.append({"role": "assistant", "content": text})
            spine.record_llm_meta(fallback_metadata)
            spine.post_verify({"ok": True, "message": "tool_chain summary"})
            return self._enrich_response(
                {
                    "reply": text,
                    "tool_trace": tool_trace,
                    "plan": plan,
                    "auto_warn": self._maybe_warn_from_trace(chain_trace),
                    "advice": advice,
                    "citations": advice.get("citations", []),
                    "token_usage": token_usage,
                    "model_used": fallback_metadata.get("fallback_model")
                    if fallback_metadata.get("fallback_used")
                    else self.model,
                    "fallback_used": fallback_metadata.get("fallback_used", False),
                    "fallback_metadata": fallback_metadata,
                },
                spine,
            )

        # 通用路径：注入编排提示 + LLM 自主多轮调工具
        planner_note = format_plan_for_llm(plan)
        
        # 阶段2: 感知环境（通用路径）
        spine.stage("environment_probe", {
            "intent": plan["intent"],
            "planner_note": planner_note[:500],
            "grounding_length": len(grounding),
            "system_context": system_ctx[:500],
        })
        self._history.append(
            build_react_user_message(user_message, grounding, system_ctx, planner_note),
        )

        fallback_metadata = {"fallback_used": False}
        for round_idx in range(self.max_tool_rounds):
            # 最后一轮禁止再调工具，促使模型基于已有观测收束回答
            tools_arg = self.tools if round_idx < self.max_tool_rounds - 1 else None
            tool_choice = "auto" if tools_arg else "none"
            # 使用带 fallback 的客户端
            try:
                response, fallback_metadata = self._fallback_client.chat_completion(
                    messages=self._history,
                    tools=tools_arg,
                    tool_choice=tool_choice,
                )
            except (BudgetExpiredError, Exception) as e:
                return await self._degraded_or_error(
                    spine,
                    user_message,
                    plan,
                    tool_trace,
                    token_usage,
                    e,
                    fallback_metadata=fallback_metadata,
                )

            choice = response.choices[0]
            msg = choice.message
            self._note_llm_call(spine, token_usage, response)

            if choice.finish_reason != "tool_calls" or not msg.tool_calls:
                text = self._finalize_llm_text(msg.content or "", user_message)
                self._history.append({"role": "assistant", "content": text})
                
                # 阶段4: 安全校验（LLM决策）
                spine.stage("safety_check", {
                    "model": fallback_metadata.get("fallback_model") if fallback_metadata.get("fallback_used") else self.model,
                    "fallback_used": fallback_metadata.get("fallback_used", False),
                    "response_length": len(text),
                    "finish_reason": choice.finish_reason,
                })
                
                # 阶段5: 执行结果
                spine.record_llm_meta(fallback_metadata)
                spine.stage("execution", {
                    "reply_length": len(text),
                    "token_usage": token_usage,
                    "tool_trace_count": len(tool_trace),
                })
                spine.post_verify({"ok": True, "message": "llm direct reply"})
                return self._enrich_response(
                    {
                        "reply": text,
                        "tool_trace": tool_trace,
                        "plan": plan,
                        "auto_warn": self._maybe_warn_from_trace(tool_trace),
                        "citations": search_knowledge(user_message, top_k=3),
                        "token_usage": token_usage,
                        "model_used": fallback_metadata.get("fallback_model")
                        if fallback_metadata.get("fallback_used")
                        else self.model,
                        "fallback_used": fallback_metadata.get("fallback_used", False),
                        "fallback_metadata": fallback_metadata,
                    },
                    spine,
                )

            self._history.append(msg.model_dump())
            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                output = await self.executor.call_tool(name, args)
                clipped = truncate_observation(output)
                tool_trace.append({"tool": name, "args": args, "output": clipped})
                spine.stage(
                    "execution",
                    {"tool": name, "output_len": len(output), "preview": clipped[:120]},
                )
                spine.post_verify(
                    {"ok": "[错误]" not in output[:80], "tool": name, "message": clipped[:200]},
                )
                self._history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": clipped,
                    }
                )
            self._apply_react_context_budget()

        return self._enrich_response(
            {
                "reply": "已达到最大工具轮次，请缩小问题后重试。",
                "tool_trace": tool_trace,
                "plan": plan,
                "auto_warn": False,
                "token_usage": token_usage,
                "model_used": self.model,
            },
            spine,
        )

    def _maybe_warn_from_trace(self, tool_trace: list[dict[str, Any]]) -> bool:
        for item in tool_trace:
            if item.get("tool") not in ("query_security_scan", "query_security_scan_json"):
                continue
            try:
                raw = item.get("output", "")
                if item["tool"] == "query_security_scan_json":
                    data = json.loads(raw)
                elif "run_full_security_check" in str(tool_trace):
                    data = json.loads(raw).get("scan", {})
                else:
                    continue
                return should_auto_warn(data.get("risks", []))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return False

    @staticmethod
    def risk_summary_from_scan(scan_data: dict[str, Any]) -> dict[str, int]:
        return summarize_risks(scan_data.get("risks", []))


def _extract_risks_from_tool_output(tool_out: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(tool_out)
        if isinstance(data, dict) and "risks" in data:
            return data.get("risks", [])
        if isinstance(data, dict) and "scan" in data:
            return data.get("scan", {}).get("risks", [])
    except json.JSONDecodeError:
        pass
    return []

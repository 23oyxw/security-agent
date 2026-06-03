"""Agent 运维规则与工作流（注入 LLM，非 Cursor Skills 格式）."""

from __future__ import annotations

from security_agent import config

# 自动化等级说明（供文档与 UI 展示）
AUTOMATION_LEVEL = {
    "level": "L3 — 自主编排 + 规则门控终端",
    "auto_scan": True,
    "auto_warn": True,
    "auto_block": False,
    "auto_report": True,
    "autonomous_workflow": True,
    "terminal_allowlist": True,
    "max_tool_rounds": config.REACT_MAX_TOOL_ROUNDS,
}

OPERATION_RULES: list[str] = [
    "拦截进程前必须先 list_processes 或 query_security_scan 确认高危，除非用户明确说「强制拦截」.",
    "不得编造 PID、路径或扫描结果；工具无输出时如实说明.",
    "终止进程属于高危操作：一次只处理一个 PID，并说明原因.",
    "权限不足时告知用户需 root/管理员，并给出 sudo 命令示例，不要假装已成功.",
    "监控可建议启动，但默认不代替用户长期开启，除非用户明确要求.",
]

WORKFLOW_STEPS: list[str] = [
    "1. 感知：scan / list_processes / get_monitor_events",
    "2. 评估：按严重/高/中等级分类，引用 policy 建议",
    "3. 建议：输出处置方案，询问是否拦截或生成报告",
    "4. 执行：仅在用户确认后调用 block_high_risk_process",
    "5. 留痕：拦截与扫描会自动写入审计日志",
]


def build_system_prompt_extension() -> str:
    rules = "\n".join(f"- {r}" for r in OPERATION_RULES)
    flow = "\n".join(WORKFLOW_STEPS)
    auto = AUTOMATION_LEVEL
    return f"""
## 运维规则
{rules}

## 标准工作流
{flow}

## 自动化边界
- 可自动：扫描、列表、报告、监控查询、风险告警提示
- 不可自动：杀进程（auto_block={auto['auto_block']}），须用户明确授权
- 工具最多连续调用 {auto['max_tool_rounds']} 轮
"""

"""基于检索 + 实盘风险的结构化建议 — 人性化、可执行、防误删."""

from __future__ import annotations

from typing import Any

from security_agent.agent.policy import classify_risk, recommend_action
from security_agent.knowledge.playbooks import PLAYBOOK_BY_ID
from security_agent.retrieval.hybrid import format_grounding_block, search_knowledge


def build_query_from_context(user_message: str, risks: list[dict[str, Any]] | None = None) -> str:
    parts = [user_message]
    if risks:
        types = " ".join({r.get("type", "") for r in risks[:8]})
        parts.append(types)
        if any("高危" in str(r.get("type", "")) for r in risks):
            parts.append("进程 误删 kill")
        if any("权限" in str(r.get("type", "")) for r in risks):
            parts.append("root 权限 shadow")
    return " ".join(parts)


def build_structured_advice(
    user_message: str,
    *,
    risks: list[dict[str, Any]] | None = None,
    tool_summary: str = "",
    top_k: int = 5,
) -> dict[str, Any]:
    query = build_query_from_context(user_message, risks)
    hits = search_knowledge(query, top_k=top_k)

    # 按风险类型补检索
    if risks:
        for r in risks[:3]:
            tag = _risk_to_tag(r)
            if tag:
                extra = search_knowledge(r.get("message", "") or r.get("type", ""), top_k=2, threat_tag=tag)
                seen = {h["id"] for h in hits}
                for e in extra:
                    if e["id"] not in seen:
                        hits.append(e)
                        seen.add(e["id"])

    hits = hits[:top_k]
    grounding = format_grounding_block(hits)

    conclusion = _conclusion_from_risks(risks)
    steps: list[str] = []
    do_not: list[str] = []
    citations = [h["id"] for h in hits]
    needs_confirm = any(h.get("requires_root_confirm") for h in hits)

    for h in hits:
        do_not.extend(h.get("do_not", [])[:2])
        steps.extend(h.get("suggested_actions", [])[:2])

    if risks:
        for r in risks[:5]:
            steps.append(recommend_action(r))
            lvl = classify_risk(r)
            if lvl.value in ("严重", "高"):
                needs_confirm = True

    if not risks and not tool_summary:
        conclusion = "建议先执行扫描或描述具体现象，再给出处置意见。"
        steps.append("可调用 query_security_scan 或 run_full_security_check")

    do_not = list(dict.fromkeys(do_not))[:6]
    steps = list(dict.fromkeys(steps))[:8]

    return {
        "conclusion": conclusion,
        "steps": steps,
        "do_not": do_not,
        "citations": citations,
        "requires_user_confirmation": needs_confirm,
        "grounding_text": grounding,
        "knowledge_hits": hits,
        "playbook_titles": [PLAYBOOK_BY_ID[c].title for c in citations if c in PLAYBOOK_BY_ID],
    }


def format_advice_for_user(advice: dict[str, Any]) -> str:
    lines = [f"**结论**：{advice.get('conclusion', '')}"]
    if advice.get("steps"):
        lines.append("\n**建议步骤**")
        for i, s in enumerate(advice["steps"], 1):
            lines.append(f"{i}. {s}")
    if advice.get("do_not"):
        lines.append("\n**请勿**")
        for d in advice["do_not"]:
            lines.append(f"- {d}")
    if advice.get("requires_user_confirmation"):
        lines.append("\n⚠️ 涉及 root/拦截/写操作，须在界面勾选确认后执行。")
    cites = advice.get("citations") or []
    if cites:
        lines.append(f"\n*依据知识库：{', '.join(cites)}*")
    return "\n".join(lines)


def _conclusion_from_risks(risks: list[dict[str, Any]] | None) -> str:
    if not risks:
        return "当前无结构化风险项；若您担心误报或漏报，可先跑综合体检。"
    n = len(risks)
    critical = sum(1 for r in risks if classify_risk(r).value == "严重")
    high = sum(1 for r in risks if classify_risk(r).value == "高")
    if critical:
        return f"发现 {n} 项风险，其中 {critical} 项严重，建议先隔离再处置，勿未确认就删进程。"
    if high:
        return f"发现 {n} 项风险，含 {high} 项高危，建议逐项核对后再拦截。"
    return f"发现 {n} 项风险，多为中低危，可按优先级排期处理。"


def _risk_to_tag(risk: dict[str, Any]) -> str | None:
    t = risk.get("type", "")
    msg = (risk.get("message") or "").lower()
    if "高危进程" in t:
        return "misdelete" if "演练" in msg else "exfiltration"
    if "权限" in t:
        return "privilege"
    if "连接" in t or "端口" in t:
        return "port_exposure"
    return None

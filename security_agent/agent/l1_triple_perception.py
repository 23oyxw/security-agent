"""L1 三感知 — 并行模块（analyze 阶段专用，零工具零执行）.

1. 抗性边界感知 — 对抗训练 + 权限跃迁阻力对抗训练
2. 灵敏知识库检索 — 规范/流程/故障/调度/工具规范
3. 静态环境感知（眼）— 网络/端口/CPU/内存/磁盘/链路/权限/状态
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

TRIPLE_PERCEPTION_META = [
    {
        "id": "adversarial_boundary",
        "title": "抗性边界感知",
        "short": "边界",
        "description": "对抗训练边界校验 · 权限跃迁阻力 · 越界识别",
        "wiki_sink": "gitee-wiki://boundary-adversarial",
    },
    {
        "id": "sensitive_knowledge",
        "title": "灵敏知识库检索",
        "short": "知识",
        "description": "规范 · 流程 · 故障 · 调度 · 工具说明高灵敏检索",
        "wiki_sink": "gitee-wiki://knowledge-index",
    },
    {
        "id": "static_environment_eye",
        "title": "静态环境感知（眼）",
        "short": "静态",
        "description": "网络 · 端口 · CPU · 内存 · 磁盘 · 链路 · 权限 · 系统状态",
        "wiki_sink": "gitee-wiki://static-perception",
    },
]

# 权限跃迁阻力 — 对抗训练探针（边界矩阵 + 跃迁阻力集）
_PRIVILEGE_ESCALATION_PROBES = [
    ("PE-01", "sudo 提权未确认", r"\bsudo\b(?!.*(status|cat|grep|journalctl))"),
    ("PE-02", "su 切换身份", r"\bsu\s+-"),
    ("PE-03", "SUID/setuid 修改", r"chmod\s+[ug]?[+-=]?[sS]"),
    ("PE-04", "passwd 改密", r"\bpasswd\b"),
    ("PE-05", "账户创建/删除", r"\b(useradd|userdel|usermod)\b"),
    ("PE-06", "root 属主变更", r"chown\s+root"),
    ("PE-07", "iptables 清空", r"iptables\s+-F"),
    ("PE-08", "管道远程执行", r"\|\s*(bash|sh)\b"),
    ("PE-09", "capabilities 提权", r"\b(setcap|cap_setuid|cap_sys_admin)\b"),
    ("PE-10", "ACL 权限篡改", r"\b(setfacl|chattr\s+\+i?)\b"),
    ("PE-11", "挂载敏感路径", r"\b(mount\s+/|umount\s+/)\b"),
    ("PE-12", "反向 shell 特征", r"\b(nc\s+-e|/dev/tcp/|bash\s+-i\s*>\s*&)\b"),
    ("PE-13", "cron 持久化", r"\b(crontab\s+-e|/etc/cron\.)\b"),
    ("PE-14", "SSH 密钥植入", r"(\>\>\s*~/.ssh/authorized_keys|ssh-keygen.*-f)"),
]

# L1 知识检索 — 意图关键词扩展（规范/流程/故障/调度/工具）
_INTENT_EXPANSIONS: dict[str, list[str]] = {
    "规范": ["playbook", "policy", "合规", "PB-"],
    "流程": ["流程", "步骤", "runbook", "处置"],
    "故障": ["故障", "修复", "repair", "异常", "宕机"],
    "调度": ["调度", "schedule", "cron", "资源", "nice"],
    "工具": ["工具", "mcp", "terminal", "命令", "白名单"],
    "边界": ["边界", "越界", "deny", "sudo", "权限"],
    "入侵": ["入侵", "后门", "webshell", "exfiltration", "IOC"],
    "加固": ["加固", "hardening", "ssh", "防火墙"],
}


def _detect_intent_tags(message: str) -> list[str]:
    text = message.lower()
    tags: list[str] = []
    for tag, kws in _INTENT_EXPANSIONS.items():
        if tag in message or any(kw in text for kw in kws):
            tags.append(tag)
    if not tags and len(message.strip()) > 2:
        tags.append("通用")
    return tags[:6]


def _expand_query(message: str, intent_hint: str | None = None) -> str:
    tags = _detect_intent_tags(message)
    if intent_hint and intent_hint not in tags:
        tags.insert(0, intent_hint)
    extra: list[str] = []
    for tag in tags:
        extra.extend(_INTENT_EXPANSIONS.get(tag, [])[:2])
    if not extra:
        return message
    return f"{message} {' '.join(dict.fromkeys(extra))}"


async def run_adversarial_boundary_perception(message: str) -> dict[str, Any]:
    """抗性边界感知：用户输入 + 对抗样本 + 权限跃迁阻力."""
    from security_agent.agent.orchestrator import _extract_shell_command
    from security_agent.rules.engine import check_terminal, check_tool

    hits: list[dict[str, Any]] = []
    cmd = _extract_shell_command(message) or message.strip()

    if cmd:
        r = check_terminal(cmd, user_confirmed=False)
        hits.append({
            "type": "terminal",
            "input": cmd,
            "verdict": r.verdict.value,
            "reasons": list(r.reasons or []),
            "source": "rule_engine",
        })

    privilege_probes: list[dict[str, Any]] = []
    text = message.lower()
    for probe_id, label, pattern in _PRIVILEGE_ESCALATION_PROBES:
        if re.search(pattern, text, re.IGNORECASE):
            privilege_probes.append({
                "probe_id": probe_id,
                "label": label,
                "matched": True,
                "resistance": "privilege_escalation_guard",
            })

    adversarial_calibration: dict[str, Any] = {}
    live_probes: list[dict[str, Any]] = []
    try:
        from security_agent.demo.boundary import run_terminal_boundary_tests, summarize_boundary

        rows = run_terminal_boundary_tests()
        adversarial_calibration = summarize_boundary(rows)
        adversarial_calibration["matrix_source"] = "demo/boundary.py"
        adversarial_calibration["resistance_training"] = "权限跃迁阻力对抗训练集"

        # 对用户输入做抽样对抗：若含 shell 片段则对照矩阵同类用例
        if cmd and len(cmd) > 3:
            r_live = check_terminal(cmd, user_confirmed=False)
            live_probes.append({
                "input": cmd,
                "verdict": r_live.verdict.value,
                "expected_categories": ["终端-允许", "终端-拒绝", "终端-需确认", "终端-非白名单"],
                "matrix_pass_rate": adversarial_calibration.get("pass_rate"),
            })
    except Exception as e:
        adversarial_calibration = {"error": str(e)}

    risk_level = "low"
    if privilege_probes or any(h.get("verdict") in ("DENY", "QUARANTINE") for h in hits):
        risk_level = "high"
    elif any(h.get("verdict") == "NEED_CONFIRM" for h in hits):
        risk_level = "medium"

    return {
        "module": "adversarial_boundary",
        "title": "抗性边界感知",
        "hits": hits,
        "privilege_escalation_probes": privilege_probes,
        "live_adversarial_probes": live_probes,
        "adversarial_calibration": adversarial_calibration,
        "risk_level": risk_level,
        "probe_count": len(_PRIVILEGE_ESCALATION_PROBES),
        "wiki_target": "gitee-wiki://boundary-adversarial",
        "constraint": "只感知不执行",
    }


async def run_sensitive_knowledge_retrieval(
    message: str,
    *,
    top_k: int = 5,
    intent_hint: str | None = None,
) -> dict[str, Any]:
    """灵敏知识库检索：高灵敏 hybrid 检索 + 意图扩展 + playbook 兜底."""
    refs: list[dict[str, Any]] = []
    sensitivity = "normal"
    intent_tags = _detect_intent_tags(message)
    if intent_hint and intent_hint not in intent_tags:
        intent_tags.insert(0, intent_hint)
    expanded_query = _expand_query(message, intent_hint)

    try:
        from security_agent.retrieval.hybrid import search_knowledge

        raw = search_knowledge(expanded_query, top_k=top_k)
        seen_ids: set[str] = set()
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("id") or item.get("title") or "")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            score = float(item.get("score") or 0)
            if score >= 0.75:
                sensitivity = "high"
            elif score >= 0.45 and sensitivity != "high":
                sensitivity = "medium"
            refs.append({
                "id": item.get("id"),
                "title": item.get("title") or item.get("id") or "条目",
                "snippet": (item.get("body") or item.get("excerpt") or item.get("content") or item.get("text") or "")[:320],
                "source": item.get("source") or "knowledge",
                "score": score,
                "category": item.get("category") or (item.get("threat_tags") or ["general"])[0],
                "severity": item.get("severity"),
                "suggested_actions": (item.get("suggested_actions") or [])[:3],
                "do_not": (item.get("do_not") or [])[:2],
            })
    except Exception:
        pass

    if len(refs) < top_k // 2:
        try:
            from security_agent.knowledge.playbooks import PLAYBOOKS

            q = expanded_query.lower()
            for pb in PLAYBOOKS:
                if len(refs) >= top_k:
                    break
                searchable = f"{pb.id} {pb.title} {pb.body} {' '.join(pb.keywords)}".lower()
                if any(tok in searchable for tok in q.split() if len(tok) > 1):
                    if pb.id in {r.get("id") for r in refs}:
                        continue
                    refs.append({
                        "id": pb.id,
                        "title": pb.title,
                        "snippet": (pb.body or "")[:320],
                        "source": "playbook",
                        "score": 0.55,
                        "category": pb.threat_tags[0] if pb.threat_tags else "playbook",
                        "severity": pb.severity,
                        "suggested_actions": list(pb.suggested_actions)[:3],
                        "do_not": list(pb.do_not)[:2],
                    })
        except Exception:
            pass

    brief: dict[str, Any] = {}
    try:
        from security_agent.pipeline.knowledge_contract import format_knowledge_brief

        brief = format_knowledge_brief(refs[:top_k])
    except Exception:
        pass

    return {
        "module": "sensitive_knowledge",
        "title": "灵敏知识库检索",
        "refs": refs[:top_k],
        "brief": brief,
        "hit_count": len(refs[:top_k]),
        "sensitivity": sensitivity,
        "intent_tags": intent_tags,
        "expanded_query": expanded_query[:500],
        "wiki_target": "gitee-wiki://knowledge-index",
        "constraint": "只检索不执行",
    }


async def run_static_environment_eye() -> dict[str, Any]:
    """静态环境感知（眼）：系统快照 + 多维环境读数."""
    snapshot: dict[str, Any] = {}
    dimensions: dict[str, Any] = {}

    try:
        from security_agent.agent.perception import get_proactive_snapshot

        snapshot = get_proactive_snapshot() or {}
    except Exception as e:
        snapshot = {"error": str(e)}

    summary = snapshot.get("summary") if isinstance(snapshot, dict) else {}
    if isinstance(summary, dict):
        dimensions = {
            "cpu": summary.get("cpu_percent"),
            "memory": summary.get("memory_percent"),
            "disk": summary.get("disk_percent"),
            "network": summary.get("network") or summary.get("connections"),
            "ports": summary.get("open_ports") or summary.get("port_count"),
            "processes": summary.get("process_count"),
            "permissions": summary.get("permission_flags"),
            "health": summary.get("system_health"),
        }

    return {
        "module": "static_environment_eye",
        "title": "静态环境感知（眼）",
        "snapshot": snapshot,
        "dimensions": {k: v for k, v in dimensions.items() if v is not None},
        "eye_axes": ["网络", "端口", "CPU", "内存", "磁盘", "链路", "权限", "状态"],
        "wiki_target": "gitee-wiki://static-perception",
        "constraint": "只读监听",
    }


async def run_triple_perception_parallel(message: str) -> dict[str, Any]:
    """L1 三感知并行入口."""
    boundary, knowledge, static_eye = await asyncio.gather(
        run_adversarial_boundary_perception(message),
        run_sensitive_knowledge_retrieval(message),
        run_static_environment_eye(),
    )
    return {
        "parallel": True,
        "modules": TRIPLE_PERCEPTION_META,
        "adversarial_boundary": boundary,
        "sensitive_knowledge": knowledge,
        "static_environment_eye": static_eye,
    }

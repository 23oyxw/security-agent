"""统一知识索引 — Playbook + Wiki 双源结构化检索.

多维度分段存储:
  facet:risk_level      — 🔴严重高危 / 🟠高风险 / 🟡中风险 / 辅助
  facet:scenario        — 检测 / 溯源 / 加固 / 拦截 / 审计
  facet:command_type    — 原生命令 / 开源工具 / 攻防特征
  facet:os_layer        — 应用层 / 内核层 / 网络层 / 文件系统
  facet:source          — playbook / wiki

检索接口:
  search(q, facet_filters, top_k) → [{id, title, body, facets, score, actions}]
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.knowledge.playbooks import PLAYBOOKS, Playbook

_TOKEN = re.compile(r"[\w一-鿿]+", re.UNICODE)
INDEX_PATH = config.DATA_DIR / "knowledge_index.json"


# ============================================================
# 中文→英文查询扩展 (语义桥)
# ============================================================
ZH_EN_MAP = {
    "端口": ["port"], "日志": ["log","audit"], "进程": ["process"],
    "账号": ["user","account","sudo","uid"], "权限": ["permission","privilege","suid","chmod","chown"],
    "暴力": ["bruteforce","ssh","fail2ban"], "破解": ["bruteforce","ssh","fail2ban"],
    "后门": ["backdoor","rootkit","shell"], "webshell": ["webshell","webshell"],
    "shell": ["reverse_shell","shell"], "木马": ["trojan","rootkit","backdoor"],
    "入侵": ["intrusion","attack","hack"], "提权": ["privilege","suid","sudo"],
    "加固": ["hardening"], "防火墙": ["firewall","iptables"],
    "检测": ["detection","sigma","yara"], "扫描": ["scan","scan"],
    "监控": ["monitoring","monitor"], "审计": ["audit","auditd"],
    "完整性": ["integrity","integrity"], "哈希": ["hash","md5sum","sha256"],
    "备份": ["backup","snapshot"], "回滚": ["rollback","restore"],
    "清理": ["cleanup","clean"], "网络": ["network","network"],
    "连接": ["connection","network"], "磁盘": ["disk","disk"],
    "内存": ["memory","memory"], "cpu": ["cpu","cpu"],
    "负载": ["load","cpu"], "数据": ["data","exfiltration"],
    "窃密": ["exfiltration","data"], "外联": ["exfiltration","network"],
    "封禁": ["iptables","block"], "定时任务": ["crontab","persistence"],
    "反弹": ["reverse_shell","nc","socat"], "命令": ["command","bash","shell"],
    "sudo": ["sudo","sudoers","privilege"], "suid": ["suid","find","chmod"],
    "ssh": ["ssh","sshd_config","port"], "fail2ban": ["fail2ban","iptables"],
}


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text) if len(t) > 1}


def _expand_query(tokens: set[str]) -> set[str]:
    """将中文词展开为英文等价词."""
    expanded = set(tokens)
    for t in tokens:
        if t in ZH_EN_MAP:
            expanded.update(ZH_EN_MAP[t])
    return expanded


def _score_doc(query_tokens: set[str], doc, *, expanded: set[str]) -> float:
    """多维度打分 — 中英双通道."""
    if isinstance(doc, Playbook):
        title_t = _tokenize(doc.title)
        body_t = _tokenize(doc.body)
        keys_t = {k.lower() for k in doc.keywords}
        tags_t = {t.lower().replace('_', ' ') for t in doc.threat_tags}
    else:
        title_t = _tokenize(doc.title)
        body_t = _tokenize(doc.content)
        tags_doc = {t.lower() for t in (doc.tags or [])}
        keys_t = tags_doc | {doc.category.lower()} if doc.category else set()
        tags_t = tags_doc

    # 中文原词 × 英文扩展词 双通道
    raw_title = len(query_tokens & title_t) * 3.5
    exp_title = len(expanded & title_t) * 2.5 + len(query_tokens & tags_t) * 3.0 + len(expanded & tags_t) * 2.0
    exp_body = len(expanded & body_t) * 0.8
    exp_keys = len(expanded & keys_t) * 3.5

    return raw_title + exp_title + exp_body + exp_keys


def search_structured(
    query: str,
    *,
    top_k: int = 8,
    risk_level: str | None = None,
    scenario: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """结构化检索 — 带 facet 过滤."""
    q_tokens = _tokenize(query)
    expanded = _expand_query(q_tokens)

    # Playbook 分层分类映射
    PB_FACETS = {
        "PB-MISDELETE": {"risk_level":"中风险","scenario":"拦截","command_type":"原生命令","os_layer":"应用层"},
        "PB-EXFIL": {"risk_level":"高风险","scenario":"检测","command_type":"原生命令","os_layer":"网络层"},
        "PB-PORT": {"risk_level":"中风险","scenario":"加固","command_type":"原生命令","os_layer":"网络层"},
        "PB-PERM": {"risk_level":"高风险","scenario":"加固","command_type":"原生命令","os_layer":"文件系统"},
        "PB-AUDIT": {"risk_level":"中风险","scenario":"审计","command_type":"原生命令","os_layer":"应用层"},
        "PB-MONITOR": {"risk_level":"辅助","scenario":"检测","command_type":"原生命令","os_layer":"应用层"},
        "PB-ADVICE": {"risk_level":"辅助","scenario":"审计","command_type":"原生命令","os_layer":"应用层"},
        "PB-BT-HUNT": {"risk_level":"严重高危","scenario":"溯源","command_type":"开源工具","os_layer":"应用层"},
        "PB-BT-SIGMA": {"risk_level":"高风险","scenario":"检测","command_type":"开源工具","os_layer":"应用层"},
        "PB-BT-SCAN": {"risk_level":"中风险","scenario":"检测","command_type":"开源工具","os_layer":"网络层"},
        "PB-BT-KB": {"risk_level":"辅助","scenario":"检测","command_type":"开源工具","os_layer":"应用层"},
        "PB-BT-API": {"risk_level":"中风险","scenario":"拦截","command_type":"开源工具","os_layer":"应用层"},
        "PB-BT-LOG": {"risk_level":"中风险","scenario":"溯源","command_type":"开源工具","os_layer":"应用层"},
        "PB-BT-IR": {"risk_level":"严重高危","scenario":"溯源","command_type":"原生命令","os_layer":"应用层"},
        "PB-BT-WAF": {"risk_level":"高风险","scenario":"拦截","command_type":"开源工具","os_layer":"应用层"},
        "PB-BT-AUDIT": {"risk_level":"中风险","scenario":"审计","command_type":"开源工具","os_layer":"内核层"},
        "PB-BT-SYS": {"risk_level":"中风险","scenario":"加固","command_type":"开源工具","os_layer":"内核层"},
        "PB-BT-NET": {"risk_level":"中风险","scenario":"加固","command_type":"开源工具","os_layer":"网络层"},
        "PB-BT-IDS": {"risk_level":"高风险","scenario":"检测","command_type":"开源工具","os_layer":"网络层"},
        "PB-BT-TI": {"risk_level":"高风险","scenario":"检测","command_type":"开源工具","os_layer":"应用层"},
    }

    # 收集结果
    items: list[tuple[float, dict[str, Any]]] = []

    # 1. Playbook
    for pb in PLAYBOOKS:
        score = _score_doc(q_tokens, pb, expanded=expanded)
        if score <= 0:
            continue
        facet = PB_FACETS.get(pb.id, {"risk_level":"中风险","scenario":"检测","command_type":"原生命令","os_layer":"应用层"})
        # facet 过滤
        if risk_level and facet.get("risk_level") != risk_level:
            continue
        if scenario and facet.get("scenario") != scenario:
            continue

        items.append((score, {
            "id": pb.id, "title": pb.title, "source": "playbook",
            "body": pb.body, "excerpt": pb.body[:280],
            "score": round(score, 3), "severity": pb.severity,
            "keywords": list(pb.keywords), "threat_tags": list(pb.threat_tags),
            "do_not": list(pb.do_not), "suggested_actions": list(pb.suggested_actions),
            "facet": facet,
        }))

    # 2. Gitee Wiki
    try:
        from security_agent.knowledge.gitee_wiki.indexer import WikiIndexer
        wiki = WikiIndexer()
        if wiki.load() or wiki.is_loaded():
            for doc in wiki._docs[:50]:
                score = _score_doc(q_tokens, doc, expanded=expanded)
                if score <= 0:
                    continue
                wiki_facet = {
                    "risk_level": "高风险" if any(t in (doc.tags or []) for t in ["webshell","反弹shell","rootkit"]) else "中风险",
                    "scenario": "检测",
                    "command_type": "开源工具" if any(kw in doc.title for kw in ["lynis","aide","rkhunter"]) else "原生命令",
                    "os_layer": "应用层",
                }
                if risk_level and wiki_facet.get("risk_level") != risk_level:
                    continue
                if scenario and wiki_facet.get("scenario") != scenario:
                    continue

                items.append((score, {
                    "id": f"WIKI-{doc.title[:20]}", "title": doc.title, "source": "wiki",
                    "body": doc.content, "excerpt": doc.content[:280],
                    "score": round(score, 3), "severity": "中",
                    "keywords": doc.tags or [], "threat_tags": doc.tags or [],
                    "do_not": [], "suggested_actions": [],
                    "facet": wiki_facet,
                }))
    except Exception:
        pass

    # 排序 & 返回
    items.sort(key=lambda x: -x[0])
    results = []
    for _, item in items[:top_k]:
        results.append(item)

    # 统计 facet 分布
    facet_counts = {"risk_level": Counter(), "scenario": Counter(), "command_type": Counter(), "source": Counter()}
    for item in results:
        f = item.get("facet", {})
        for dim in facet_counts:
            val = f.get(dim, "其他")
            facet_counts[dim][val] += 1

    return rerank_hits(query, results, top_k=top_k)


def list_facets() -> dict[str, Any]:
    """返回所有可用的 facet 选项."""
    return {
        "risk_level": ["严重高危", "高风险", "中风险", "辅助"],
        "scenario": ["检测", "溯源", "加固", "拦截", "审计"],
        "command_type": ["原生命令", "开源工具", "攻防特征"],
        "os_layer": ["应用层", "内核层", "网络层", "文件系统"],
        "source": ["playbook", "wiki"],
    }

def rerank_hits(query: str, hits: list[dict[str, Any]], *, top_k: int | None = None) -> list[dict[str, Any]]:
    """Lightweight rerank: boost title/tag overlap on top of retrieval score."""
    if not hits:
        return []
    q_tokens = _tokenize(query)
    expanded = _expand_query(q_tokens)
    rescored: list[tuple[float, dict[str, Any]]] = []
    for hit in hits:
        title_t = _tokenize(hit.get("title", ""))
        tags_t = {t.lower() for t in hit.get("threat_tags", [])}
        bonus = len(q_tokens & title_t) * 0.8 + len(expanded & tags_t) * 0.5
        base = float(hit.get("score") or 0)
        item = dict(hit)
        item["score"] = round(base + bonus, 3)
        item["rerank_bonus"] = round(bonus, 3)
        rescored.append((item["score"], item))
    rescored.sort(key=lambda x: -x[0])
    out = [item for _, item in rescored]
    if top_k is not None:
        return out[:top_k]
    return out

"""混合检索 — 关键词 + 标签 + 可选向量，为 Agent 提供 grounding 上下文."""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.knowledge.playbooks import PLAYBOOKS, Playbook

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
_INDEX_PATH = config.DATA_DIR / "knowledge_vectors.json"


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text) if len(t) > 1}


def _keyword_score(query: str, doc: Playbook) -> float:
    """多维度关键词匹配 + 中英映射 + 部分匹配."""
    q = _tokenize(query)
    if not q:
        return 0.0

    title = _tokenize(doc.title)
    body = _tokenize(doc.body)
    keys = {k.lower() for k in doc.keywords}
    tags = {t.lower().replace('_', ' ') for t in doc.threat_tags}

    # 中英双向映射
    zh_en = {
        "端口": ["port"], "日志": ["log","audit"], "进程": ["process"],
        "账号": ["user","account","sudo","uid"], "权限": ["permission","privilege","suid","chmod","chown"],
        "暴力": ["bruteforce","ssh","fail2ban"], "破解": ["bruteforce","ssh","fail2ban"],
        "后门": ["backdoor","rootkit","shell"], "webshell": ["webshell","webshell"],
        "shell": ["reverse_shell","shell"], "木马": ["trojan","rootkit","backdoor"],
        "入侵": ["intrusion","attack","hack"], "提权": ["privilege","suid","sudo"],
        "加固": ["hardening","hardening"], "防火墙": ["firewall","iptables"],
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
    }

    expanded_tags = set(tags)
    for qt in q:
        if qt in zh_en:
            for en in zh_en[qt]:
                expanded_tags.add(en)

    hit_title = len(q & title) * 3.0
    hit_body = len(q & body) * 1.0
    hit_keys = len(q & keys) * 4.0

    hit_tags = 0.0
    for qt in q:
        if qt in expanded_tags:
            hit_tags += 2.5
        else:
            for tag in expanded_tags:
                if qt in tag or tag in qt:
                    hit_tags += 1.5
                    break

    return hit_title + hit_body + hit_keys + hit_tags


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _load_vector_index() -> dict[str, list[float]]:
    if not _INDEX_PATH.exists():
        return {}
    try:
        data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in data.get("vectors", {}).items()}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("向量索引加载失败: %s", exc)
        return {}


def _get_embedding_client():
    """获取嵌入专用客户端：优先 EMBEDDING_*，回退 LLM_*."""
    from openai import OpenAI

    api_key = config.EMBEDDING_API_KEY or config.LLM_API_KEY
    base_url = config.EMBEDDING_BASE_URL if config.EMBEDDING_API_KEY else config.LLM_BASE_URL
    return OpenAI(api_key=api_key, base_url=base_url)


def _embed_query(text: str) -> list[float] | None:
    if not config.RAG_USE_EMBEDDINGS:
        return None
    if not config.EMBEDDING_API_KEY and not config.llm_configured():
        return None
    try:
        client = _get_embedding_client()
        resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=text[:2000])
        return list(resp.data[0].embedding)
    except Exception as exc:
        logger.warning("向量嵌入失败（回退关键词检索）: %s", exc)
        return None


def build_vector_index(*, force: bool = False) -> dict[str, Any]:
    """构建/更新向量索引（需 API）；失败时仍可用关键词检索."""
    config.ensure_data_dirs()
    if _INDEX_PATH.exists() and not force:
        return {"ok": True, "message": "索引已存在", "path": str(_INDEX_PATH)}

    if not config.EMBEDDING_API_KEY and not config.llm_configured():
        return {"ok": False, "message": "未配置 API Key，仅使用关键词检索"}

    try:
        client = _get_embedding_client()
        vectors: dict[str, list[float]] = {}
        for pb in PLAYBOOKS:
            text = f"{pb.title}\n{pb.body}\n{' '.join(pb.keywords)}"
            resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=text[:2000])
            vectors[pb.id] = list(resp.data[0].embedding)
        _INDEX_PATH.write_text(
            json.dumps({"vectors": vectors, "model": config.EMBEDDING_MODEL}, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"ok": True, "count": len(vectors), "path": str(_INDEX_PATH)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": str(exc)}


def search_knowledge(
    query: str,
    *,
    top_k: int = 8,
    threat_tag: str | None = None,
    risk_level: str | None = None,
    scenario: str | None = None,
) -> list[dict[str, Any]]:
    """统一结构化检索 — 委托给 knowledge_index 引擎."""
    from security_agent.retrieval.knowledge_index import search_structured

    results = search_structured(query, top_k=top_k, risk_level=risk_level, scenario=scenario)
    if threat_tag:
        results = [r for r in results if threat_tag in r.get("threat_tags", [])]
    return results


def format_grounding_block(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "【知识库】未命中相关条目；请基于工具结果回答，勿编造。\n"
    lines = ["【知识库 grounding — 回答必须引用下列编号，不得臆造】"]
    for h in hits:
        lines.append(
            f"- [{h['id']}] {h['title']}（{h['severity']}）\n"
            f"  {h['excerpt']}\n"
            f"  建议: {'; '.join(h['suggested_actions'][:3]) or '见正文'}\n"
            f"  禁止: {'; '.join(h['do_not'][:2]) or '无'}"
        )
    return "\n".join(lines) + "\n"

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
    q = _tokenize(query)
    if not q:
        return 0.0
    title = _tokenize(doc.title)
    body = _tokenize(doc.body)
    keys = {k.lower() for k in doc.keywords}
    tags = {t.lower() for t in doc.threat_tags}
    hit_title = len(q & title) * 3.0
    hit_body = len(q & body) * 1.0
    hit_keys = len(q & keys) * 4.0
    hit_tags = len(q & tags) * 2.5
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
    top_k: int = 5,
    threat_tag: str | None = None,
    keyword_weight: float = 0.55,
    vector_weight: float = 0.45,
) -> list[dict[str, Any]]:
    """返回带分数与引用的知识条目."""
    index = _load_vector_index()
    q_vec = _embed_query(query) if index and config.RAG_USE_EMBEDDINGS else None

    scored: list[tuple[float, Playbook]] = []
    for pb in PLAYBOOKS:
        if threat_tag and threat_tag not in pb.threat_tags:
            continue
        kw = _keyword_score(query, pb)
        vec = 0.0
        if q_vec and pb.id in index:
            vec = _cosine(q_vec, index[pb.id])
        if index and q_vec:
            score = keyword_weight * kw + vector_weight * vec * 10.0
        else:
            score = kw
        if score > 0:
            scored.append((score, pb))

    scored.sort(key=lambda x: -x[0])
    out: list[dict[str, Any]] = []
    for score, pb in scored[:top_k]:
        out.append(
            {
                "id": pb.id,
                "title": pb.title,
                "score": round(score, 3),
                "severity": pb.severity,
                "threat_tags": list(pb.threat_tags),
                "requires_root_confirm": pb.requires_root_confirm,
                "excerpt": pb.body[:280],
                "do_not": list(pb.do_not),
                "suggested_actions": list(pb.suggested_actions),
            }
        )
    return out


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

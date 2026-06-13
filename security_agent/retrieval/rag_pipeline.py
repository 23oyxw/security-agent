"""RAG six-stage pipeline status (lightweight, no Ragas dependency)."""

from __future__ import annotations

from typing import Any

from security_agent import config


def _stage(id_: str, name: str, status: str, impl: str, note: str = "") -> dict[str, str]:
    return {"id": id_, "name": name, "status": status, "impl": impl, "note": note}


def get_rag_pipeline_status() -> dict[str, Any]:
    from security_agent.knowledge.playbooks import PLAYBOOKS

    has_index = (config.DATA_DIR / "knowledge_index.json").exists()
    has_vectors = (config.DATA_DIR / "knowledge_vectors.json").exists()
    embeddings_on = config.RAG_USE_EMBEDDINGS

    stages = [
        _stage("ingest", "入库分片", "ok", "playbooks + gitee_wiki/indexer", f"{len(PLAYBOOKS)} playbooks"),
        _stage("semantic_chunk", "语义分片", "ok" if has_index else "partial", "knowledge_index facet 五维", "risk/scenario/os_layer"),
        _stage("hybrid_retrieve", "混合检索", "ok", "knowledge_index + hybrid.py", "关键词 + 中英扩展"),
        _stage("rerank", "轻量 Rerank", "ok", "knowledge_index.rerank_hits", "标题/标签加权重排"),
        _stage("grounding", "Grounding 契约", "ok", "format_grounding_block", "编号引用防幻觉"),
        _stage("eval", "质量评测", "planned", "Ragas (optional)", "龙芯环境建议关闭重型依赖"),
    ]

    vector_status = "on" if embeddings_on and has_vectors else ("off" if not embeddings_on else "partial")
    return {
        "pipeline": "rag_six_stage",
        "stages": stages,
        "completed": sum(1 for s in stages if s["status"] == "ok"),
        "total": len(stages),
        "embeddings": vector_status,
        "rag_use_embeddings": embeddings_on,
    }
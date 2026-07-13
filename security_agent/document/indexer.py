"""双路检索引擎 — 关键词(BM25-like) + 向量(TF-IDF cosine)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from security_agent.document.chunker import Chunk
from security_agent.document.embedder import TFIDFEmbedder


@dataclass
class SearchResult:
    """一条检索结果."""
    chunk: Chunk
    score: float          # 0.0 ~ 1.0
    match_type: str        # "keyword" | "vector" | "hybrid"
    keywords_matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = self.chunk.to_dict()
        d["score"] = round(self.score, 4)
        d["match_type"] = self.match_type
        d["keywords_matched"] = self.keywords_matched[:10]
        return d


class DualIndexer:
    """双路检索：关键词 + 向量混合.

    检索流程:
        1. 关键词路: BM25 风格评分 → top_k_results
        2. 向量路: TF-IDF cosine → top_k_results
        3. 合并: 两路结果加权融合排序
    """

    def __init__(self):
        self._chunks: list[Chunk] = []
        self._embedder: TFIDFEmbedder = TFIDFEmbedder()
        self._vectors: list[dict[int, float]] = []   # 与 _chunks 一一对应
        self._keyword_index: dict[str, set[int]] = {}  # word → {chunk_indices}
        self._fitted = False

    def index(self, chunks: list[Chunk]) -> int:
        """索引一组文档块.

        Returns:
            索引的块数量
        """
        if not chunks:
            return 0

        start_idx = len(self._chunks)
        self._chunks.extend(chunks)

        # 构建关键词倒排索引
        for i, chunk in enumerate(chunks):
            tokens = self._embedder._tokenize(chunk.text)
            for token in set(tokens):
                if token not in self._keyword_index:
                    self._keyword_index[token] = set()
                self._keyword_index[token].add(start_idx + i)

        # 构建/更新 TF-IDF
        all_texts = [c.text for c in self._chunks]
        self._embedder.fit(all_texts)
        self._vectors = [self._embedder.transform(text) for text in all_texts]
        self._fitted = True

        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        keyword_weight: float = 0.4,
        vector_weight: float = 0.6,
    ) -> list[SearchResult]:
        """混合检索.

        Args:
            query: 查询文本
            top_k: 返回结果数
            keyword_weight: 关键词权重
            vector_weight: 向量权重
        """
        if not self._fitted or not self._chunks:
            return []

        # 1. 关键词检索
        kw_results = self._keyword_search(query, top_k * 2)

        # 2. 向量检索
        vec_results = self._vector_search(query, top_k * 2)

        # 3. 加权融合
        merged: dict[int, float] = {}
        for idx, score in kw_results:
            merged[idx] = merged.get(idx, 0) + score * keyword_weight
        for idx, score in vec_results:
            merged[idx] = merged.get(idx, 0) + score * vector_weight

        # 4. 排序+截断
        ranked = sorted(merged.items(), key=lambda x: -x[1])[:top_k]

        results = []
        for idx, score in ranked:
            chunk = self._chunks[idx]
            query_tokens = set(self._embedder._tokenize(query))
            chunk_tokens = set(self._embedder._tokenize(chunk.text))
            matched = list(query_tokens & chunk_tokens)

            # 判断匹配类型
            kw_hit = idx in dict(kw_results)
            vec_hit = idx in dict(vec_results)
            if kw_hit and vec_hit:
                match_type = "hybrid"
            elif kw_hit:
                match_type = "keyword"
            else:
                match_type = "vector"

            results.append(SearchResult(
                chunk=chunk,
                score=min(score, 1.0),
                match_type=match_type,
                keywords_matched=matched,
            ))

        return results

    def _keyword_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """关键词检索（BM25 简化版）."""
        query_tokens = self._embedder._tokenize(query)
        if not query_tokens:
            return []

        scores: dict[int, float] = {}
        avg_dl = sum(len(c.text.split()) for c in self._chunks) / max(len(self._chunks), 1)
        N = len(self._chunks)
        k1, b = 1.5, 0.75

        for token in set(query_tokens):
            if token not in self._keyword_index:
                continue
            matching = self._keyword_index[token]
            df = len(matching)
            idf = __import__('math').log((N - df + 0.5) / (df + 0.5) + 1)

            for idx in matching:
                chunk = self._chunks[idx]
                tf = chunk.text.lower().count(token.lower())
                dl = len(chunk.text.split())
                score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
                scores[idx] = scores.get(idx, 0) + score

        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]

    def _vector_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """向量检索."""
        q_vec = self._embedder.transform(query)
        if not q_vec:
            return []

        scores = []
        for i, vec in enumerate(self._vectors):
            sim = self._embedder.similarity(q_vec, vec)
            if sim > 0:
                scores.append((i, sim))

        return sorted(scores, key=lambda x: -x[1])[:top_k]

    def get_keywords(self, chunk_idx: int, top_k: int = 5) -> list[tuple[str, float]]:
        """获取指定块的关键词."""
        if chunk_idx >= len(self._chunks):
            return []
        return self._embedder.keywords(self._chunks[chunk_idx].text, top_k)

    def stats(self) -> dict[str, Any]:
        return {
            "total_chunks": len(self._chunks),
            "vocab_size": self._embedder.vocab_size,
            "keyword_index_terms": len(self._keyword_index),
            "fitted": self._fitted,
        }

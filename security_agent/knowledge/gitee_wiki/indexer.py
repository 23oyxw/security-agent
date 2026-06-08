"""轻量向量索引生成器 — 关键词 + 余弦相似度混合检索.

无外部嵌入模型依赖，使用 jieba 分词 + TF-IDF 构建关键词向量。
sentence-transformers 可选增强（若已安装且显式启用）。

复用 security_agent/retrieval/hybrid.py 的 _tokenize / _cosine 模式。
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.knowledge.gitee_wiki.models import WikiDoc

logger = logging.getLogger(__name__)

# 索引存储路径
INDEX_PATH = config.DATA_DIR / "gitee_wiki_index.json"
CACHE_PATH = config.DATA_DIR / "gitee_wiki_cache.json"

# 中文 + 英文分词正则
_TOKEN_RE = re.compile(r"[\w一-鿿]+", re.UNICODE)

# 尝试加载 jieba（可选依赖）
try:
    import jieba

    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False
    jieba = None  # type: ignore


def _tokenize(text: str) -> list[str]:
    """分词：中文用 jieba，英文用正则."""
    if not text:
        return []
    if _JIEBA_AVAILABLE and jieba is not None:
        # jieba 分词（保留长度 > 1 的词）
        words = jieba.lcut(text)
        return [w.strip().lower() for w in words if len(w.strip()) > 1]
    # 回退：正则分词
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1]


def _tfidf_vectorize(
    docs: list[list[str]],
    vocabulary: dict[str, int],
    dim: int,
) -> list[list[float]]:
    """TF-IDF 向量化."""
    n = len(docs)
    # TF
    tfs: list[dict[int, float]] = []
    for tokens in docs:
        counter = Counter(tokens)
        total = len(tokens) or 1
        tf = {}
        for word, count in counter.items():
            idx = vocabulary.get(word)
            if idx is not None:
                tf[idx] = count / total
        tfs.append(tf)

    # IDF
    idf = [0.0] * dim
    for i, word in enumerate(vocabulary):
        doc_count = sum(1 for tf in tfs if i in tf)
        idf[i] = math.log((n + 1) / (doc_count + 1)) + 1.0

    # TF-IDF 向量
    vectors = []
    for tf in tfs:
        vec = [0.0] * dim
        for idx, val in tf.items():
            vec[idx] = val * idf[idx]
        # L2 归一化
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])

    return vectors


def _cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _keyword_score(query: str, doc: WikiDoc) -> float:
    """关键词匹配得分."""
    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return 0.0
    title = set(_tokenize(doc.title))
    body = set(_tokenize(doc.content))
    tags = {t.lower() for t in doc.tags}
    cat = set(_tokenize(doc.category))

    return (
        len(q_tokens & title) * 3.0
        + len(q_tokens & cat) * 2.5
        + len(q_tokens & tags) * 4.0
        + len(q_tokens & body) * 1.0
    )


class WikiIndexer:
    """Wiki 知识库索引器.

    用法:
        indexer = WikiIndexer()
        docs = [WikiDoc(...), ...]
        indexer.build_index(docs)
        results = indexer.search("SSH 暴力破解", top_k=5)
    """

    def __init__(self, index_path: Path | str | None = None):
        self._index_path = Path(index_path) if isinstance(index_path, str) else (index_path or INDEX_PATH)
        self._docs: list[WikiDoc] = []
        self._vectors: list[list[float]] = []
        self._vocabulary: dict[str, int] = {}
        self._built_at: str = ""

    # ---- 构建索引 ----

    def build_index(self, docs: list[WikiDoc]) -> int:
        """构建向量索引并持久化到磁盘."""
        if not docs:
            logger.warning("无文档，跳过索引构建")
            return 0

        import time

        # 分词
        tokenized = [_tokenize(d.search_text) for d in docs]

        # 构建词汇表
        all_tokens: set[str] = set()
        for tokens in tokenized:
            all_tokens.update(tokens)
        vocab_list = sorted(all_tokens)
        self._vocabulary = {word: i for i, word in enumerate(vocab_list)}

        # TF-IDF 向量
        self._vectors = _tfidf_vectorize(tokenized, self._vocabulary, len(vocab_list))
        self._docs = docs
        self._built_at = time.strftime("%Y-%m-%dT%H:%M:%S")

        # 持久化
        self._save()

        logger.info(
            "索引构建完成: %d 篇文档, %d 维词汇表, 保存至 %s",
            len(docs),
            len(self._vocabulary),
            self._index_path,
        )
        return len(docs)

    def _save(self) -> None:
        """保存索引到 JSON."""
        data = {
            "built_at": self._built_at,
            "doc_count": len(self._docs),
            "docs": [d.to_dict() for d in self._docs],
            "vocabulary": self._vocabulary,
            "vectors": self._vectors,
        }
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self) -> bool:
        """从磁盘加载索引."""
        if not self._index_path.exists():
            return False
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._built_at = data.get("built_at", "")
            self._docs = [WikiDoc.from_dict(d) for d in data.get("docs", [])]
            self._vocabulary = data.get("vocabulary", {})
            self._vectors = data.get("vectors", [])
            logger.info("索引已加载: %d 篇文档, built_at=%s", len(self._docs), self._built_at)
            return True
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("索引文件损坏: %s", e)
            return False

    def is_loaded(self) -> bool:
        return len(self._docs) > 0

    # ---- 检索 ----

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """混合检索：向量相似度 + 关键词匹配.

        Args:
            query: 检索查询
            category: 按分类过滤（可选）
            top_k: 返回结果数

        Returns:
            [{"title": ..., "score": ..., "category": ..., "snippet": ..., ...}, ...]
        """
        if not self._docs or not self._vectors:
            if not self.load():
                return []

        # 对查询向量化
        query_tokens = _tokenize(query)
        query_counter = Counter(query_tokens)
        total = len(query_tokens) or 1
        query_vec = [0.0] * len(self._vocabulary)
        for word, count in query_counter.items():
            idx = self._vocabulary.get(word)
            if idx is not None:
                query_vec[idx] = count / total

        # L2 归一化
        norm = math.sqrt(sum(v * v for v in query_vec)) or 1.0
        query_vec = [v / norm for v in query_vec]

        # 混合打分
        scores: list[tuple[int, float]] = []
        for i, (doc, vec) in enumerate(zip(self._docs, self._vectors)):
            if category and doc.category != category:
                continue
            vector_score = _cosine(query_vec, vec) * 10.0
            keyword_score = _keyword_score(query, doc)
            combined = vector_score + keyword_score
            scores.append((i, combined))

        # 排序
        scores.sort(key=lambda x: -x[1])
        results = []
        for idx, score in scores[:top_k]:
            if score <= 0:
                continue
            doc = self._docs[idx]
            results.append({
                "title": doc.title,
                "category": doc.category,
                "tags": doc.tags,
                "score": round(score, 3),
                "snippet": doc.content[:300].replace("\n", " "),
                "updated_at": doc.updated_at,
                "source_url": doc.source_url,
            })

        return results

    def list_categories(self) -> list[dict[str, Any]]:
        """列出所有分类及文档数."""
        if not self._docs:
            if not self.load():
                return []

        counter: Counter[str] = Counter()
        for doc in self._docs:
            counter[doc.category] += 1

        return [
            {"category": cat, "doc_count": count}
            for cat, count in counter.most_common()
        ]

    def get_doc(self, title: str) -> dict[str, Any] | None:
        """按标题精确查找文档."""
        if not self._docs:
            if not self.load():
                return None

        for doc in self._docs:
            if doc.title == title:
                return {
                    "title": doc.title,
                    "category": doc.category,
                    "tags": doc.tags,
                    "content": doc.content,
                    "updated_at": doc.updated_at,
                    "source_url": doc.source_url,
                }
        return None

    @property
    def status(self) -> dict[str, Any]:
        return {
            "built_at": self._built_at,
            "doc_count": len(self._docs),
            "vocab_size": len(self._vocabulary),
        }


# ---- 缓存管理 ----

def save_cache(docs: list[WikiDoc], path: Path | str | None = None) -> None:
    """保存 Wiki 文档到本地 JSON 缓存."""
    p = Path(path) if isinstance(path, str) else (path or CACHE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {"docs": [d.to_dict() for d in docs], "count": len(docs)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("缓存已保存: %d 篇文档 → %s", len(docs), p)


def load_cache(path: Path | str | None = None) -> list[WikiDoc]:
    """从本地 JSON 缓存加载 Wiki 文档."""
    p = Path(path) if isinstance(path, str) else (path or CACHE_PATH)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [WikiDoc.from_dict(d) for d in data.get("docs", [])]
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("缓存文件损坏: %s", e)
        return []

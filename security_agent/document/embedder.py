"""向量嵌入 — TF-IDF 默认 + OpenAI 可选.

设计原则（渐进式）:
    默认使用本地 TF-IDF（零外部依赖，麒麟 LoongArch 可用），
    可选配置 OpenAI embedding 获得更好精度。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


class TFIDFEmbedder:
    """轻量 TF-IDF 向量化 — 零外部依赖，麒麟 LoongArch 即装即用.

    词表大小约 10K-50K 个词，每个文档向量维度 = 词表大小（稀疏）。
    对于几百到几千份文档的检索场景足够。
    """

    def __init__(self, max_features: int = 10000):
        self.max_features = max_features
        self._vocabulary: dict[str, int] = {}     # word → index
        self._idf: dict[str, float] = {}          # word → idf
        self._doc_count = 0

    def fit(self, documents: list[str]) -> "TFIDFEmbedder":
        """在文档集合上构建词汇表和 IDF."""
        # 统计词频
        doc_freq: Counter[str] = Counter()
        tokenized = []
        for doc in documents:
            tokens = self._tokenize(doc)
            tokenized.append(tokens)
            doc_freq.update(set(tokens))
        self._doc_count = len(documents)

        # 构建词汇表（按频率排序，取 top N）
        top_words = [w for w, _ in doc_freq.most_common(self.max_features)]
        self._vocabulary = {w: i for i, w in enumerate(top_words)}

        # 计算 IDF
        for word, idx in self._vocabulary.items():
            df = doc_freq.get(word, 1)
            self._idf[word] = math.log((self._doc_count + 1) / (df + 1)) + 1

        return self

    def transform(self, text: str) -> dict[int, float]:
        """单文档 → 稀疏向量 {word_index: tfidf_score}."""
        tokens = self._tokenize(text)
        if not tokens:
            return {}

        tf = Counter(tokens)
        max_tf = max(tf.values()) if tf else 1
        vector: dict[int, float] = {}

        for word, count in tf.items():
            if word in self._vocabulary:
                idx = self._vocabulary[word]
                tf_norm = count / max_tf
                vector[idx] = tf_norm * self._idf.get(word, 1.0)

        return vector

    def similarity(self, v1: dict[int, float], v2: dict[int, float]) -> float:
        """两个稀疏向量的余弦相似度."""
        # 只计算两个向量都有的维度
        common = set(v1.keys()) & set(v2.keys())
        if not common:
            # 尝试全维度计算
            dot = sum(v1.get(i, 0) * v2.get(i, 0) for i in set(v1.keys()) | set(v2.keys()))
            if dot == 0:
                return 0.0
            norm1 = math.sqrt(sum(v * v for v in v1.values()))
            norm2 = math.sqrt(sum(v * v for v in v2.values()))
            return dot / (norm1 * norm2) if norm1 * norm2 > 0 else 0.0

        dot = sum(v1[i] * v2[i] for i in common)
        norm1 = math.sqrt(sum(v * v for v in v1.values()))
        norm2 = math.sqrt(sum(v * v for v in v2.values()))
        return dot / (norm1 * norm2) if norm1 * norm2 > 0 else 0.0

    def keywords(self, text: str, top_k: int = 5) -> list[tuple[str, float]]:
        """提取文本的关键词."""
        tokens = self._tokenize(text)
        if not tokens:
            return []
        tf = Counter(tokens)
        scored = [(w, tf[w] * self._idf.get(w, 1.0)) for w in set(tokens) if w in self._vocabulary]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """中文+英文混合分词 — 多粒度保证短文本也有足够 token."""
        tokens = []
        # 中文: 2-4 字短语（语义单元）
        chinese_phrases = re.findall(r'[一-鿿]{2,4}', text)
        tokens.extend(chinese_phrases)
        # 中文: 单字回退（保证短文本至少有 token）
        chinese_single = re.findall(r'[一-鿿]', text)
        if len(chinese_phrases) < 5:
            tokens.extend(chinese_single)
        # 英文/数字小写后按非字母切分
        english = re.sub(r'[^\w\s]', ' ', text.lower())
        english_tokens = [w for w in english.split() if len(w) >= 2 and not w.isdigit()]
        tokens.extend(english_tokens)
        return tokens

    @property
    def vocab_size(self) -> int:
        return len(self._vocabulary)

    def status(self) -> dict[str, Any]:
        return {
            "vocab_size": self.vocab_size,
            "doc_count": self._doc_count,
            "max_features": self.max_features,
        }

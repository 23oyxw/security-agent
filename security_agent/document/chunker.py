"""语义分块 — 按文档结构切分，而非固定 token 数."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """一个文档片段."""
    chunk_id: str
    text: str
    source_path: str = ""
    section_title: str = ""     # 所属章节标题
    chunk_index: int = 0        # 在文档中的序号
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source": self.source_path,
            "section": self.section_title,
            "index": self.chunk_index,
            "text_preview": self.text[:300],
            "char_count": len(self.text),
            "metadata": self.metadata,
        }


class SemanticChunker:
    """基于文档结构的分块器.

    分块策略（优先级从高到低）:
        1. Markdown 标题 (# ## ###)
        2. 空行（段落边界）
        3. 固定大小（兜底，~2000 字符/块）
    """

    def __init__(self, max_chunk_chars: int = 2000, min_chunk_chars: int = 80):
        self.max_chars = max_chunk_chars
        self.min_chars = min_chunk_chars

    def chunk(self, text: str, source_path: str = "", title: str = "") -> list[Chunk]:
        """将文本切分为语义块.

        Args:
            text: 文档全文
            source_path: 文档来源路径
            title: 文档标题

        Returns:
            有序的 Chunk 列表
        """
        if not text.strip():
            return []

        # 策略 1: 尝试按 Markdown 标题分块
        md_chunks = self._chunk_by_headings(text, source_path)
        if len(md_chunks) >= 2:
            return self._refine_chunks(md_chunks, source_path)

        # 策略 2: 按空行（段落）分块
        para_chunks = self._chunk_by_paragraphs(text, source_path)
        if len(para_chunks) >= 2:
            return self._refine_chunks(para_chunks, source_path)

        # 策略 3: 固定大小
        return self._chunk_by_size(text, source_path)

    def _chunk_by_headings(self, text: str, source: str) -> list[Chunk]:
        """按 Markdown 标题 (# ## ###) 分块."""
        # 找到所有标题位置
        heading_pattern = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
        matches = list(heading_pattern.finditer(text))

        if not matches:
            return []

        chunks = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()
            section_title = m.group(2).strip()

            if len(section_text) >= self.min_chars:
                chunks.append(Chunk(
                    chunk_id=f"{source}:s{i}",
                    text=section_text,
                    source_path=source,
                    section_title=section_title,
                    chunk_index=i,
                ))

        return chunks

    def _chunk_by_paragraphs(self, text: str, source: str) -> list[Chunk]:
        """按空行分块，合并相邻短段落."""
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        buffer = ""
        idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(buffer) + len(para) < self.max_chars:
                buffer += "\n\n" + para if buffer else para
            else:
                if len(buffer) >= self.min_chars:
                    chunks.append(Chunk(
                        chunk_id=f"{source}:p{idx}",
                        text=buffer.strip(),
                        source_path=source,
                        chunk_index=idx,
                    ))
                    idx += 1
                buffer = para

        if len(buffer) >= self.min_chars:
            chunks.append(Chunk(
                chunk_id=f"{source}:p{idx}",
                text=buffer.strip(),
                source_path=source,
                chunk_index=idx,
            ))

        return chunks

    def _chunk_by_size(self, text: str, source: str) -> list[Chunk]:
        """固定大小分块（兜底策略）."""
        chunks = []
        for i in range(0, len(text), self.max_chars):
            segment = text[i:i + self.max_chars]
            if len(segment) >= self.min_chars:
                chunks.append(Chunk(
                    chunk_id=f"{source}:b{i//self.max_chars}",
                    text=segment,
                    source_path=source,
                    chunk_index=i // self.max_chars,
                ))
        return chunks

    def _refine_chunks(self, chunks: list[Chunk], source: str) -> list[Chunk]:
        """细化分块：过大的块递归拆分."""
        refined = []
        idx = 0
        for chunk in chunks:
            if len(chunk.text) > self.max_chars * 1.5:
                # 对过大的块按段落再分
                sub = self._chunk_by_paragraphs(chunk.text, f"{source}:{chunk.chunk_id}")
                for s in sub:
                    s.chunk_index = idx
                    idx += 1
                    refined.append(s)
            else:
                chunk.chunk_index = idx
                idx += 1
                refined.append(chunk)
        return refined

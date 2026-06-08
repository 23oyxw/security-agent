"""Gitee Wiki 知识库 — 数据模型."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class WikiDoc:
    """单篇 Wiki 文档."""

    title: str
    category: str
    tags: list[str] = field(default_factory=list)
    content: str = ""
    updated_at: str = ""  # ISO 时间戳
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WikiDoc:
        return cls(
            title=data.get("title", ""),
            category=data.get("category", ""),
            tags=data.get("tags", []),
            content=data.get("content", ""),
            updated_at=data.get("updated_at", ""),
            source_url=data.get("source_url", ""),
        )

    @property
    def doc_id(self) -> str:
        """用于索引的唯一标识."""
        return self.title

    @property
    def search_text(self) -> str:
        """拼接用于检索的文本."""
        return f"{self.title} {self.category} {' '.join(self.tags)} {self.content}"

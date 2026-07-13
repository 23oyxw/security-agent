"""文档解析基类."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedDocument:
    """解析后的文档 — 纯文本 + 元数据."""
    source_path: str
    title: str = ""
    text: str = ""
    format: str = "unknown"          # "text" | "markdown" | "pdf" | "docx" | "log" | "conf"
    metadata: dict[str, Any] = field(default_factory=dict)
    parse_errors: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return len(self.text.split()) if self.text else 0

    @property
    def char_count(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_path,
            "title": self.title,
            "format": self.format,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "metadata": self.metadata,
            "text_preview": self.text[:500],
        }


class BaseParser:
    """文档解析器基类."""

    supported_formats: list[str] = []
    _registry: dict[str, type["BaseParser"]] = {}

    @classmethod
    def register(cls, parser_cls: type["BaseParser"]) -> type["BaseParser"]:
        for fmt in parser_cls.supported_formats:
            cls._registry[fmt] = parser_cls
        return parser_cls

    @classmethod
    def get_parser(cls, file_path: str | Path) -> "BaseParser | None":
        """根据文件后缀自动选择解析器."""
        suffix = Path(file_path).suffix.lower()
        # 无后缀 → 尝试内容检测
        if not suffix:
            return TextParser()
        # 去掉点
        fmt = suffix.lstrip(".")
        parser_cls = cls._registry.get(fmt)
        if parser_cls:
            return parser_cls()
        # 无专用解析器 → 文本解析器兜底
        return TextParser()

    def parse(self, file_path: str | Path) -> ParsedDocument:
        raise NotImplementedError

    def parse_text(self, text: str, source: str = "inline") -> ParsedDocument:
        """直接解析文本（无需文件）."""
        raise NotImplementedError

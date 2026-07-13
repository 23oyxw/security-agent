"""文档解析器 — 支持多种格式的自动检测和解析."""

from security_agent.document.parsers.base import BaseParser, ParsedDocument
from security_agent.document.parsers.text import TextParser

__all__ = ["BaseParser", "ParsedDocument", "TextParser"]

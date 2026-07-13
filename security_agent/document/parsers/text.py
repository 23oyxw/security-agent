"""文本/Markdown 解析器."""

from __future__ import annotations

import re
from pathlib import Path

from security_agent.document.parsers.base import BaseParser, ParsedDocument


@BaseParser.register
class TextParser(BaseParser):
    """纯文本 + Markdown 解析器.

    支持: .txt, .md, .log, .conf, .json, .xml, .yaml, .yml, .csv, .ini, .cfg, .sh, .py, .js
    """

    supported_formats = [
        "txt", "md", "markdown", "log", "conf", "json", "xml",
        "yaml", "yml", "csv", "ini", "cfg", "sh", "py", "js",
        "html", "css", "toml", "rst",
    ]

    def parse(self, file_path: str | Path) -> ParsedDocument:
        fp = Path(file_path)
        title = fp.stem

        try:
            text = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = fp.read_text(encoding="gbk")
            except UnicodeDecodeError:
                return ParsedDocument(
                    source_path=str(fp),
                    title=title,
                    format="unknown",
                    parse_errors=["无法解码文件编码"],
                )

        return self._build(fp, text, title)

    def parse_text(self, text: str, source: str = "inline") -> ParsedDocument:
        return self._build(Path(source), text, Path(source).stem)

    def _build(self, fp: Path, text: str, title: str) -> ParsedDocument:
        suffix = fp.suffix.lower().lstrip(".")

        # 尝试提取 markdown 标题
        if suffix in ("md", "markdown"):
            m = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
            if m:
                title = m.group(1).strip()

        # 对于 log 格式，尝试提取时间戳范围
        metadata = {}
        if suffix == "log":
            timestamps = re.findall(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', text)
            if timestamps:
                metadata["first_event"] = timestamps[0]
                metadata["last_event"] = timestamps[-1]
                metadata["event_count"] = len(timestamps)
            metadata["log_lines"] = len(text.splitlines())

        # 对于 conf/ini/cfg，统计配置项数量
        if suffix in ("conf", "ini", "cfg"):
            config_lines = [l for l in text.splitlines()
                          if l.strip() and not l.strip().startswith("#") and not l.strip().startswith(";")]
            metadata["config_entries"] = len(config_lines)

        # 对于 JSON，记录顶层键
        if suffix == "json":
            try:
                import json
                data = json.loads(text)
                if isinstance(data, dict):
                    metadata["top_keys"] = list(data.keys())[:20]
                elif isinstance(data, list):
                    metadata["array_length"] = len(data)
            except json.JSONDecodeError:
                metadata["valid_json"] = False

        return ParsedDocument(
            source_path=str(fp),
            title=title,
            text=text,
            format=suffix,
            metadata=metadata,
        )

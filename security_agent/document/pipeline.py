"""DocumentPipeline — 文档智能全链路编排.

设计原则（渐进式 + 自愈优先）:
    一条 pipeline 完成: 发现文档 → 解析 → 分块 → 索引 → 可检索

用法:
    from security_agent.document import DocumentPipeline

    pipe = DocumentPipeline()
    pipe.ingest("/path/to/doc.md")       # 摄入单份文档
    pipe.ingest_dir("/var/log/reports")  # 批量摄入目录
    results = pipe.search("磁盘清理")     # 检索
    delta = pipe.learn_from_incident(...) # 从安全事件中抽取知识
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.document.parsers.base import BaseParser, ParsedDocument
from security_agent.document.chunker import SemanticChunker
from security_agent.document.indexer import DualIndexer, SearchResult


class DocumentPipeline:
    """文档智能处理流水线.

    数据持久化: data/document_index/ (索引) + data/knowledge_drafts/ (知识草稿)
    """

    def __init__(self):
        self._index_dir = config.DATA_DIR / "document_index"
        self._drafts_dir = config.DATA_DIR / "knowledge_drafts"
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._drafts_dir.mkdir(parents=True, exist_ok=True)

        self._chunker = SemanticChunker()
        self._indexer = DualIndexer()
        self._documents: list[ParsedDocument] = []

    # ---- 摄入 ----

    def ingest(self, path: str | Path) -> dict[str, Any]:
        """摄入一份文档：解析 → 分块 → 索引.

        Args:
            path: 文档文件路径

        Returns:
            {"ok": bool, "doc": ParsedDocument dict, "chunks": int, "indexed": bool}
        """
        fp = Path(path)
        if not fp.exists():
            return {"ok": False, "error": f"File not found: {path}"}

        # 1. 解析
        parser = BaseParser.get_parser(fp)
        if parser is None:
            return {"ok": False, "error": f"No parser for: {fp.suffix}"}

        doc = parser.parse(fp)
        if doc.parse_errors:
            return {"ok": False, "error": str(doc.parse_errors), "doc": doc.to_dict()}

        self._documents.append(doc)

        # 2. 分块
        chunks = self._chunker.chunk(doc.text, doc.source_path, doc.title)

        # 3. 索引
        count = self._indexer.index(chunks)

        return {
            "ok": True,
            "doc": doc.to_dict(),
            "chunks": count,
            "indexed": True,
        }

    def ingest_text(self, text: str, source: str = "inline", title: str = "") -> dict[str, Any]:
        """摄入纯文本（无文件）."""
        from security_agent.document.parsers.text import TextParser
        parser = TextParser()
        doc = parser.parse_text(text, source)
        if title:
            doc.title = title
        self._documents.append(doc)

        chunks = self._chunker.chunk(doc.text, doc.source_path, doc.title)
        count = self._indexer.index(chunks)

        return {"ok": True, "doc": doc.to_dict(), "chunks": count}

    def ingest_dir(self, directory: str | Path, pattern: str = "*") -> list[dict[str, Any]]:
        """批量摄入目录下所有匹配文件."""
        results = []
        for fp in Path(directory).rglob(pattern):
            if fp.is_file():
                results.append(self.ingest(fp))
        return results

    # ---- 检索 ----

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """检索相关文档片段."""
        results = self._indexer.search(query, top_k=top_k)
        return [r.to_dict() for r in results]

    def search_with_context(self, query: str, top_k: int = 5) -> dict[str, Any]:
        """检索并附带上下文."""
        results = self._indexer.search(query, top_k=top_k)
        return {
            "query": query,
            "results": [r.to_dict() for r in results],
            "total_indexed": self._indexer.stats()["total_chunks"],
            "search_time_ms": 0,  # TODO: 实际计时
        }

    # ---- 知识抽取 ----

    def learn_from_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        """从安全事件中自动抽取知识草稿.

        Args:
            incident: {"type": "安全事件类型", "root_cause": "...",
                        "resolution": "...", "severity": "高", "tags": [...]}

        Returns:
            {"draft_id": str, "draft_path": str, "keywords": [...]}
        """
        draft_id = uuid.uuid4().hex[:12]
        draft = {
            "draft_id": draft_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "incident",
            "status": "draft",             # draft → review → approved → published
            "incident": incident,
            "playbook_title": f"自动生成: {incident.get('type', '未知事件')}处置方案",
            "keywords": self._extract_keywords_from_incident(incident),
            "do_not": self._infer_do_not(incident),
            "suggested_actions": self._infer_actions(incident),
        }

        # 保存草稿
        draft_path = self._drafts_dir / f"{draft_id}.json"
        draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "draft_id": draft_id,
            "draft_path": str(draft_path),
            "keywords": draft["keywords"],
            "status": "draft",
            "note": "知识草稿已生成，待人工审核后加入知识库",
        }

    def list_drafts(self, status: str = "draft") -> list[dict[str, Any]]:
        """列出知识草稿."""
        drafts = []
        for fp in self._drafts_dir.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if data.get("status") == status or status == "all":
                    drafts.append(data)
            except (json.JSONDecodeError, KeyError):
                continue
        return sorted(drafts, key=lambda d: d.get("created_at", ""), reverse=True)

    def approve_draft(self, draft_id: str) -> dict[str, Any]:
        """审核通过知识草稿 → 标记为 approved."""
        draft_path = self._drafts_dir / f"{draft_id}.json"
        if not draft_path.exists():
            return {"ok": False, "error": f"Draft {draft_id} not found"}

        data = json.loads(draft_path.read_text(encoding="utf-8"))
        data["status"] = "approved"
        draft_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 同时摄入为可检索文档
        self.ingest_text(
            text=f"# {data['playbook_title']}\n\n{json.dumps(data, ensure_ascii=False, indent=2)}",
            source=f"knowledge:{draft_id}",
            title=data["playbook_title"],
        )

        return {"ok": True, "draft_id": draft_id, "status": "approved"}

    # ---- 统计 ----

    def stats(self) -> dict[str, Any]:
        return {
            "indexer": self._indexer.stats(),
            "documents": len(self._documents),
            "drafts": len(list(self._drafts_dir.glob("*.json"))),
        }

    # ---- 内部 ----

    @staticmethod
    def _extract_keywords_from_incident(incident: dict[str, Any]) -> list[str]:
        """从事中自动提取关键词."""
        keywords = []
        for field in ("type", "root_cause", "tags"):
            val = incident.get(field, "")
            if isinstance(val, list):
                keywords.extend(val)
            elif isinstance(val, str) and val:
                keywords.append(val)
        return keywords[:10]

    @staticmethod
    def _infer_do_not(incident: dict[str, Any]) -> list[str]:
        """根据事件类型推断「禁止事项」."""
        etype = str(incident.get("type", "")).lower()
        defaults = ["未确认根因前不要执行批量操作"]

        if "磁盘" in etype or "disk" in etype:
            defaults.append("不要直接 rm -rf，先确认文件归属")
        if "进程" in etype or "process" in etype:
            defaults.append("不要 kill -9，先尝试正常终止")
        if "网络" in etype or "network" in etype:
            defaults.append("不要直接 iptables -F，先确认规则来源")

        return defaults

    @staticmethod
    def _infer_actions(incident: dict[str, Any]) -> list[str]:
        """根据事件类型推断「建议动作」."""
        resolution = str(incident.get("resolution", ""))
        if resolution:
            return [resolution]
        return ["分析根因", "记录处置步骤", "更新知识库"]

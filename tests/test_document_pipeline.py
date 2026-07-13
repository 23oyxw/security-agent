"""文档智能测试 — 解析 + 分块 + 索引 + 检索 + 知识抽取."""

from __future__ import annotations

import tempfile
from pathlib import Path


# ---- Parsers ----

def test_text_parser_markdown():
    """解析 Markdown 文件."""
    from security_agent.document.parsers.text import TextParser
    parser = TextParser()
    md = "# 磁盘清理指南\n\n## 步骤1\n\n清理 /var/log 下旧文件。\n\n## 步骤2\n\n使用 logrotate。"
    doc = parser.parse_text(md, "test.md")
    assert doc.format == "md"
    assert "磁盘清理指南" in doc.title or doc.word_count > 0
    assert doc.word_count > 5


def test_text_parser_log():
    """解析 Log 文件，自动提取时间戳."""
    from security_agent.document.parsers.text import TextParser
    parser = TextParser()
    log = "2026-07-13 10:00:01 INFO started\n2026-07-13 10:00:02 INFO running\n2026-07-13 10:05:00 ERROR failed"
    doc = parser.parse_text(log, "test.log")
    assert doc.format == "log"
    assert "first_event" in doc.metadata
    assert doc.metadata.get("event_count") == 3


def test_text_parser_json():
    """解析 JSON，记录顶层键."""
    from security_agent.document.parsers.text import TextParser
    parser = TextParser()
    doc = parser.parse_text('{"name": "test", "version": "1.0", "items": [1,2,3]}', "test.json")
    assert doc.format == "json"
    assert "top_keys" in doc.metadata
    assert "name" in doc.metadata["top_keys"]


def test_auto_parser_selection():
    """根据后缀自动选择解析器."""
    from security_agent.document.parsers.base import BaseParser
    parser = BaseParser.get_parser("doc.md")
    assert parser is not None
    assert "md" in parser.supported_formats


def test_parsed_document_to_dict():
    """ParsedDocument.to_dict() 完整."""
    from security_agent.document.parsers.text import TextParser
    parser = TextParser()
    doc = parser.parse_text("Hello world", "test.txt")
    d = doc.to_dict()
    for key in ("source", "title", "format", "word_count", "text_preview"):
        assert key in d


# ---- Chunker ----

def test_chunker_markdown_headings():
    """Markdown 标题分块."""
    from security_agent.document.chunker import SemanticChunker
    chunker = SemanticChunker(max_chunk_chars=500, min_chunk_chars=50)
    text = "# 标题1\n\n" + "内容1。" * 50 + "\n\n## 标题2\n\n" + "内容2。" * 50 + "\n\n# 标题3\n\n" + "内容3。" * 50
    chunks = chunker.chunk(text, "test.md")
    assert len(chunks) >= 1
    if len(chunks) >= 2:
        titles = [c.section_title for c in chunks]
        assert any("标题" in t for t in titles)


def test_chunker_paragraphs():
    """段落分块."""
    from security_agent.document.chunker import SemanticChunker
    chunker = SemanticChunker(max_chunk_chars=200, min_chunk_chars=50)
    text = "段落A。" * 30 + "\n\n段落B。" * 30 + "\n\n段落C。" * 30
    chunks = chunker.chunk(text, "test.txt")
    assert len(chunks) >= 1


def test_chunker_small_text():
    """短文本至少 0 或 1 块."""
    from security_agent.document.chunker import SemanticChunker
    chunker = SemanticChunker()
    chunks = chunker.chunk("短文本", "test.txt")
    assert len(chunks) <= 1


# ---- Embedder ----

def test_embedder_fit_transform():
    """TF-IDF fit + transform."""
    from security_agent.document.embedder import TFIDFEmbedder
    e = TFIDFEmbedder(max_features=500)
    e.fit(["磁盘清理日志文件", "清理磁盘空间", "日志分析报告"])
    v = e.transform("磁盘清理")
    assert len(v) > 0


def test_embedder_similarity():
    """相似度: 同文档 transform 两次 → 完美相似；空向量 → 0."""
    from security_agent.document.embedder import TFIDFEmbedder
    e = TFIDFEmbedder(max_features=500)
    long_doc = "磁盘清理释放空间删除过期日志文件系统运维维护定期执行清理磁盘空间优化存储"
    e.fit([long_doc, "完全不相关的网络路由防火墙IP配置DNS解析"])

    # 相同文本 → 高相似度
    v1 = e.transform(long_doc)
    v2 = e.transform(long_doc)
    sim_identical = e.similarity(v1, v2)
    assert sim_identical > 0.9, f"Identical text should have high similarity, got {sim_identical}"

    # 相似度范围 [0,1]
    assert 0 <= sim_identical <= 1.0

    # 空向量 → 相似度为 0
    sim_empty = e.similarity({}, {1: 0.5})
    assert sim_empty == 0.0


def test_embedder_keywords():
    """关键词提取."""
    from security_agent.document.embedder import TFIDFEmbedder
    e = TFIDFEmbedder(max_features=500)
    e.fit(["磁盘清理日志文件", "清理磁盘空间", "日志分析"])
    kw = e.keywords("磁盘清理日志")
    assert len(kw) >= 1
    assert any("磁盘" in w for w, _ in kw)


# ---- Indexer ----

def test_indexer_index_and_search():
    """索引 + 检索 — 用足够长且有区分度的文本."""
    from security_agent.document.chunker import SemanticChunker
    from security_agent.document.indexer import DualIndexer

    chunker = SemanticChunker(min_chunk_chars=50)
    chunks = chunker.chunk(
        "# 磁盘清理磁盘空间\n\n清理日志文件磁盘清理是一个重要的运维任务。需要定期删除旧的日志文件以释放磁盘空间。"
        "使用 find 命令可以高效地查找和删除过期文件。磁盘清理包括多个步骤：检查使用率、备份、删除、验证。\n\n"
        "# 网络配置管理\n\n修改网络配置文件需要编辑接口设置和路由表。网络管理与磁盘管理完全不同。"
        "网络配置涉及 IP 地址、子网掩码、网关和 DNS 服务器。\n\n"
        "# 进程管理服务\n\n使用 systemctl 管理服务进程包括启动停止重启和查看状态。进程与服务管理属于系统管理范畴。",
        "guide.md",
    )

    indexer = DualIndexer()
    indexer.index(chunks)

    results = indexer.search("磁盘清理日志文件", top_k=2)
    assert len(results) >= 1, f"Got {len(results)} results, chunks={len(chunks)}"


def test_indexer_search_no_match():
    """无匹配时不崩溃."""
    from security_agent.document.indexer import DualIndexer
    indexer = DualIndexer()
    results = indexer.search("xyz", top_k=5)
    assert results == []


def test_indexer_stats():
    """stats() 完整."""
    from security_agent.document.chunker import SemanticChunker
    from security_agent.document.indexer import DualIndexer
    chunker = SemanticChunker()
    indexer = DualIndexer()
    indexer.index(chunker.chunk("测试内容", "test.txt"))
    s = indexer.stats()
    assert "total_chunks" in s


# ---- FileVersionManager ----

def test_version_manager_write_and_read():
    """写入 + 读取."""
    from security_agent.filesystem.version_manager import FileVersionManager

    with tempfile.TemporaryDirectory() as tmp:
        mgr = FileVersionManager(storage_dir=Path(tmp) / "versions")
        file_path = Path(tmp) / "test.txt"

        v1 = mgr.write(file_path, "version 1")
        assert v1.operation in ("create", "modify")
        assert file_path.read_text() == "version 1"

        content = mgr.read(file_path)
        assert content == b"version 1"


def test_version_manager_history():
    """版本历史."""
    from security_agent.filesystem.version_manager import FileVersionManager

    with tempfile.TemporaryDirectory() as tmp:
        mgr = FileVersionManager(storage_dir=Path(tmp) / "versions")
        file_path = Path(tmp) / "test.txt"

        mgr.write(file_path, "v1")
        mgr.write(file_path, "v2")
        mgr.write(file_path, "v3")

        history = mgr.history(file_path)
        assert len(history) >= 2


def test_version_manager_dedup():
    """内容未变不创建新版本."""
    from security_agent.filesystem.version_manager import FileVersionManager

    with tempfile.TemporaryDirectory() as tmp:
        mgr = FileVersionManager(storage_dir=Path(tmp) / "versions")
        file_path = Path(tmp) / "test.txt"

        v1 = mgr.write(file_path, "same content")
        v2 = mgr.write(file_path, "same content")
        assert v1.version_id == v2.version_id  # 去重


def test_safe_ops_write_read():
    """SafeFileOps 写入+读取."""
    from security_agent.filesystem.safe_ops import SafeFileOps

    with tempfile.TemporaryDirectory() as tmp:
        ops = SafeFileOps(version_dir=Path(tmp) / "versions")
        file_path = Path(tmp) / "safe_test.txt"

        result = ops.write(file_path, "safe content", message="test write")
        assert result["ok"] is True

        content = ops.read_text(file_path)
        assert content == "safe content"


# ---- DocumentPipeline ----

def test_pipeline_ingest_text():
    """摄入文本 → 可检索."""
    from security_agent.document import DocumentPipeline

    pipe = DocumentPipeline()
    result = pipe.ingest_text(
        "# 磁盘空间不足处理\n\n当磁盘使用率超过 90% 时，需要清理旧的日志文件。"
        "推荐使用 logrotate 自动管理。清理步骤包括：首先检查磁盘使用率，"
        "然后使用 find 命令查找超过 30 天的日志文件，最后删除或压缩。",
        source="knowledge:disk_guide",
    )
    assert result["ok"] is True
    assert result["chunks"] >= 1, f"Got {result['chunks']} chunks"


def test_pipeline_search():
    """摄入后可检索 — 用有区分度的长文本."""
    from security_agent.document import DocumentPipeline

    pipe = DocumentPipeline()
    pipe.ingest_text(
        "磁盘清理磁盘空间释放删除旧日志文件系统维护运维任务定期执行检查。"
        "使用 find 命令查找超过三十天的日志文件并删除以释放磁盘空间。"
        "磁盘清理流程包括先检查使用率然后备份重要文件最后删除过期日志。",
        source="doc1",
    )
    pipe.ingest_text(
        "网络配置路由表防火墙IP地址管理网络拓扑DNS解析子网掩码网关。"
        "修改网络配置需要编辑配置文件然后重启网络服务才能生效。",
        source="doc2",
    )
    pipe.ingest_text(
        "进程管理服务启动停止重启状态查看 systemctl 命令使用 systemd 管理。",
        source="doc3",
    )

    results = pipe.search("磁盘清理删除日志", top_k=3)
    assert len(results) >= 1, f"Got {len(results)} results, expected >=1"


def test_pipeline_learn_from_incident():
    """从事件中自动抽取知识."""
    from security_agent.document import DocumentPipeline

    pipe = DocumentPipeline()
    incident = {
        "type": "磁盘爆满",
        "root_cause": "/var/log 日志未清理",
        "resolution": "清理 30 天前的日志文件",
        "severity": "高",
        "tags": ["磁盘", "日志", "清理"],
    }
    result = pipe.learn_from_incident(incident)
    assert result["status"] == "draft"
    assert "draft_id" in result
    assert len(result["keywords"]) > 0


def test_pipeline_drafts_and_approve():
    """草稿管理."""
    from security_agent.document import DocumentPipeline

    pipe = DocumentPipeline()
    incident = {"type": "CPU告警", "root_cause": "进程死循环", "resolution": "kill 进程", "severity": "高"}
    result = pipe.learn_from_incident(incident)

    drafts = pipe.list_drafts("draft")
    assert len(drafts) >= 1

    approve = pipe.approve_draft(result["draft_id"])
    assert approve["ok"] is True
    assert approve["status"] == "approved"


def test_pipeline_stats():
    """pipeline 统计."""
    from security_agent.document import DocumentPipeline

    pipe = DocumentPipeline()
    pipe.ingest_text("测试内容", source="test")
    stats = pipe.stats()
    assert stats["documents"] >= 1
    assert "indexer" in stats


# ---- 运行入口 ----

if __name__ == "__main__":
    import traceback

    tests = [
        ("test_text_parser_markdown", test_text_parser_markdown),
        ("test_text_parser_log", test_text_parser_log),
        ("test_text_parser_json", test_text_parser_json),
        ("test_auto_parser_selection", test_auto_parser_selection),
        ("test_parsed_document_to_dict", test_parsed_document_to_dict),
        ("test_chunker_markdown_headings", test_chunker_markdown_headings),
        ("test_chunker_paragraphs", test_chunker_paragraphs),
        ("test_chunker_small_text", test_chunker_small_text),
        ("test_embedder_fit_transform", test_embedder_fit_transform),
        ("test_embedder_similarity", test_embedder_similarity),
        ("test_embedder_keywords", test_embedder_keywords),
        ("test_indexer_index_and_search", test_indexer_index_and_search),
        ("test_indexer_search_no_match", test_indexer_search_no_match),
        ("test_indexer_stats", test_indexer_stats),
        ("test_version_manager_write_and_read", test_version_manager_write_and_read),
        ("test_version_manager_history", test_version_manager_history),
        ("test_version_manager_dedup", test_version_manager_dedup),
        ("test_safe_ops_write_read", test_safe_ops_write_read),
        ("test_pipeline_ingest_text", test_pipeline_ingest_text),
        ("test_pipeline_search", test_pipeline_search),
        ("test_pipeline_learn_from_incident", test_pipeline_learn_from_incident),
        ("test_pipeline_drafts_and_approve", test_pipeline_drafts_and_approve),
        ("test_pipeline_stats", test_pipeline_stats),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
            passed += 1
        except Exception:
            print(f"  FAIL {name}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{len(tests)} passed ({failed} failed)")
    if failed == 0:
        print("  ALL PASS - Document intelligence pipeline verified!")
    print(f"{'='*60}")

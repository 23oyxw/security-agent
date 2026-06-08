"""Mem0 风格语义记忆系统 — 三级记忆架构.

参考 mem0ai/mem0 设计:
  L1 工作记忆 (Working)   — 当前对话上下文（已有 brain.py 消息）
  L2 语义记忆 (Semantic)  — 知识片段 + 嵌入向量 + 关键词索引
  L3 情节记忆 (Episodic)  — 会话摘要 + 关键决策 + 时间线

特点:
  - 无外部数据库依赖（SQLite + JSON）
  - 自动从对话中提取关键信息存入语义/情节层
  - 相似度检索复用项目已有的 _cosine / _tokenize
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from security_agent import config

# ---- 分词 ----
_TOKEN_RE = re.compile(r"[\w一-鿿]+", re.UNICODE)

try:
    import jieba
    _JIEBA = True
except ImportError:
    _JIEBA = False


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    if _JIEBA:
        return [w.strip().lower() for w in jieba.lcut(text) if len(w.strip()) > 1]
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


# ---- 数据模型 ----

@dataclass
class MemoryFragment:
    """语义记忆片段."""
    id: str
    content: str            # 知识内容
    category: str = ""      # 分类 (security/ops/troubleshooting)
    tags: list[str] = field(default_factory=list)
    importance: float = 1.0  # 0-10 重要性评分
    created_at: str = ""
    source_session: str = ""
    access_count: int = 0
    last_accessed: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EpisodeSummary:
    """情节记忆 — 会话摘要."""
    session_id: str
    summary: str            # LLM 生成的摘要
    key_decisions: list[str] = field(default_factory=list)
    threats_detected: list[str] = field(default_factory=list)
    commands_executed: list[str] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    message_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SemanticMemoryStore:
    """Mem0 风格语义记忆存储.

    架构:
      SQLite 表 fragments  — 持久化语义记忆片段
      SQLite 表 episodes   — 持久化会话情节
      JSON 索引文件        — 关键词 → fragment_id 倒排索引
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(config.DATA_DIR / "semantic_memory.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._index: dict[str, set[str]] = {}  # keyword → fragment_ids
        self._load_index()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fragments (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    importance REAL DEFAULT 1.0,
                    created_at TEXT,
                    source_session TEXT DEFAULT '',
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT DEFAULT '',
                    key_decisions TEXT DEFAULT '[]',
                    threats_detected TEXT DEFAULT '[]',
                    commands_executed TEXT DEFAULT '[]',
                    start_time TEXT DEFAULT '',
                    end_time TEXT DEFAULT '',
                    message_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fragments_category ON fragments(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fragments_importance ON fragments(importance DESC)")
            conn.commit()

    def _load_index(self) -> None:
        """加载倒排索引."""
        try:
            ipath = self.db_path.parent / "semantic_index.json"
            if ipath.exists():
                data = json.loads(ipath.read_text())
                self._index = {k: set(v) for k, v in data.items()}
        except Exception:
            self._index = {}

    def _save_index(self) -> None:
        ipath = self.db_path.parent / "semantic_index.json"
        ipath.write_text(json.dumps(
            {k: list(v) for k, v in self._index.items()},
            ensure_ascii=False,
        ))

    # ---- 语义记忆 CRUD ----

    def add(self, content: str, *, category: str = "", tags: list[str] | None = None,
            importance: float = 1.0, session_id: str = "") -> str:
        """存入一条语义记忆."""
        fid = f"mem-{time.strftime('%Y%m%d')}-{len(self._index):04x}"
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        frag = MemoryFragment(
            id=fid, content=content, category=category,
            tags=tags or [], importance=importance,
            created_at=now, source_session=session_id,
        )

        # 更新倒排索引
        tokens = _tokenize(content + " " + " ".join(tags or []))
        for t in set(tokens):
            self._index.setdefault(t, set()).add(fid)

        # 持久化
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO fragments
                   (id, content, category, tags, importance, created_at, source_session)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (fid, content, category, json.dumps(tags or [], ensure_ascii=False),
                 importance, now, session_id),
            )
            conn.commit()

        if len(self._index) % 20 == 0:
            self._save_index()
        return fid

    def search(self, query: str, top_k: int = 5,
               category: str = "") -> list[dict[str, Any]]:
        """关键词 + 倒排索引检索语义记忆."""
        q_tokens = set(_tokenize(query))
        if not q_tokens:
            return []

        # 倒排索引命中打分
        scores: dict[str, float] = {}
        for t in q_tokens:
            for fid in self._index.get(t, set()):
                scores[fid] = scores.get(fid, 0) + 1.0

        if not scores:
            return []

        # 从 DB 加载命中的 fragments
        results = []
        with sqlite3.connect(str(self.db_path)) as conn:
            for fid, kw_score in sorted(scores.items(), key=lambda x: -x[1])[:top_k * 2]:
                row = conn.execute(
                    "SELECT id, content, category, tags, importance, created_at, access_count "
                    "FROM fragments WHERE id = ?", (fid,)
                ).fetchone()
                if not row:
                    continue
                if category and row[2] != category:
                    continue

                # 混合得分：关键词命中 + 重要性加权
                importance = row[4] or 1.0
                score = kw_score * (1.0 + math.log1p(importance) * 0.3)

                # 更新访问计数
                conn.execute(
                    "UPDATE fragments SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (time.strftime("%Y-%m-%dT%H:%M:%S"), fid),
                )

                results.append({
                    "id": row[0],
                    "content": row[1][:500],
                    "category": row[2],
                    "tags": json.loads(row[3]) if row[3] else [],
                    "importance": importance,
                    "score": round(score, 3),
                    "created_at": row[5],
                    "access_count": row[6] + 1,
                })

            conn.commit()

        results.sort(key=lambda x: -x["score"])
        return results[:top_k]

    def list_by_category(self, category: str, limit: int = 20) -> list[dict[str, Any]]:
        """按分类列出记忆."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT id, content, category, tags, importance, created_at FROM fragments "
                "WHERE category = ? ORDER BY importance DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        return [
            {"id": r[0], "content": r[1][:300], "category": r[2],
             "tags": json.loads(r[3]) if r[3] else [], "importance": r[4], "created_at": r[5]}
            for r in rows
        ]

    def forget(self, fragment_id: str) -> bool:
        """删除记忆片段."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM fragments WHERE id = ?", (fragment_id,))
            conn.commit()
        for kw, fids in list(self._index.items()):
            fids.discard(fragment_id)
            if not fids:
                del self._index[kw]
        self._save_index()
        return True

    @property
    def stats(self) -> dict[str, Any]:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM fragments").fetchone()[0]
            cats = conn.execute(
                "SELECT category, COUNT(*) FROM fragments GROUP BY category"
            ).fetchall()
        return {
            "total_fragments": total,
            "categories": {c: n for c, n in cats},
            "index_terms": len(self._index),
        }

    # ---- 情节记忆 ----

    def save_episode(self, session_id: str, summary: str, *,
                     key_decisions: list[str] | None = None,
                     threats: list[str] | None = None,
                     commands: list[str] | None = None,
                     message_count: int = 0) -> None:
        """保存会话情节摘要."""
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        with sqlite3.connect(str(self.db_path)) as conn:
            # 检查是否已有记录（更新 end_time）
            existing = conn.execute(
                "SELECT start_time FROM episodes WHERE session_id = ?", (session_id,)
            ).fetchone()
            start_time = existing[0] if existing and existing[0] else now

            conn.execute(
                """INSERT OR REPLACE INTO episodes
                   (session_id, summary, key_decisions, threats_detected,
                    commands_executed, start_time, end_time, message_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, summary,
                 json.dumps(key_decisions or [], ensure_ascii=False),
                 json.dumps(threats or [], ensure_ascii=False),
                 json.dumps(commands or [], ensure_ascii=False),
                 start_time, now, message_count),
            )
            conn.commit()

    def get_episode(self, session_id: str) -> dict[str, Any] | None:
        """获取会话情节."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT * FROM episodes WHERE session_id = ?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "session_id": row[0], "summary": row[1],
            "key_decisions": json.loads(row[2]) if row[2] else [],
            "threats_detected": json.loads(row[3]) if row[3] else [],
            "commands_executed": json.loads(row[4]) if row[4] else [],
            "start_time": row[5], "end_time": row[6], "message_count": row[7],
        }

    def list_episodes(self, limit: int = 10) -> list[dict[str, Any]]:
        """列出最近的会话情节."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT session_id, summary, start_time, end_time, message_count "
                "FROM episodes ORDER BY end_time DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"session_id": r[0], "summary": r[1][:200], "start_time": r[2],
             "end_time": r[3], "message_count": r[4]}
            for r in rows
        ]

    # ---- 自动提取 ----

    def extract_from_exchange(self, user_msg: str, assistant_reply: str,
                              session_id: str = "", commands: list[str] | None = None) -> int:
        """从一轮对话中自动提取知识片段并存入语义记忆."""
        added = 0

        # 规则 1: 检测用户提到的安全威胁术语
        security_terms = {
            "暴力破解": "安全事件", "DDoS": "安全事件", "注入": "安全事件",
            "WebShell": "安全事件", "后门": "安全事件", "提权": "安全事件",
            "SSH爆破": "安全事件", "异常登录": "安全事件", "端口扫描": "安全事件",
            "CPU飙升": "故障诊断", "内存泄漏": "故障诊断", "磁盘满": "故障诊断",
            "OOM": "故障诊断", "僵尸进程": "故障诊断",
            "fail2ban": "安全加固", "iptables": "安全加固", "auditd": "安全加固",
            "SELinux": "安全加固", "AppArmor": "安全加固",
        }

        for term, cat in security_terms.items():
            if term in user_msg or term in assistant_reply:
                snippet = f"[{term}] User: {user_msg[:200]} | Response: {assistant_reply[:200]}"
                self.add(snippet, category=cat, tags=[term],
                         importance=7.0, session_id=session_id)
                added += 1

        # 规则 2: 检测执行的命令
        if commands:
            for cmd in commands:
                if any(kw in cmd for kw in ("rm ", "chmod", "chown", "kill", "iptables", "systemctl")):
                    self.add(
                        f"执行命令: {cmd} | Context: {user_msg[:100]}",
                        category="操作记录", tags=["command", "high_risk"],
                        importance=8.0, session_id=session_id,
                    )
                    added += 1

        return added


# ---- 全局单例 ----

_semantic_store: SemanticMemoryStore | None = None


def get_semantic_memory() -> SemanticMemoryStore:
    global _semantic_store
    if _semantic_store is None:
        _semantic_store = SemanticMemoryStore()
    return _semantic_store

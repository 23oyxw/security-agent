"""对话历史管理器 - 支持持久化存储"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


class ConversationMemory:
    """对话历史管理器，支持SQLite持久化存储"""
    
    def __init__(self, db_path: str = "data/conversations.db"):
        """
        初始化对话历史管理器
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation 
                ON messages(conversation_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_session 
                ON conversations(session_id)
            """)
            
            conn.commit()
    
    def create_conversation(self, session_id: str) -> int:
        """
        创建新对话
        
        Args:
            session_id: 会话ID
            
        Returns:
            对话ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO conversations (session_id) VALUES (?)",
                (session_id,)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_or_create_conversation(self, session_id: str) -> int:
        """
        获取或创建对话
        
        Args:
            session_id: 会话ID
            
        Returns:
            对话ID
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return row[0]
            else:
                return self.create_conversation(session_id)
    
    def add_message(self, session_id: str, role: str, content: str, 
                    metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        添加消息
        
        Args:
            session_id: 会话ID
            role: 角色 (system/user/assistant/tool)
            content: 消息内容
            metadata: 元数据
            
        Returns:
            消息ID
        """
        conversation_id = self.get_or_create_conversation(session_id)
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO messages (conversation_id, role, content, metadata) 
                   VALUES (?, ?, ?, ?)""",
                (conversation_id, role, content, metadata_json)
            )
            
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,)
            )
            
            conn.commit()
            return cursor.lastrowid
    
    def get_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取对话消息
        
        Args:
            session_id: 会话ID
            limit: 限制数量
            
        Returns:
            消息列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # 获取对话ID
            cursor = conn.execute(
                "SELECT id FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return []
            
            conversation_id = row[0]
            
            # 获取消息
            cursor = conn.execute(
                """SELECT role, content, metadata, timestamp 
                   FROM messages 
                   WHERE conversation_id = ? 
                   ORDER BY id DESC 
                   LIMIT ?""",
                (conversation_id, limit)
            )
            
            messages = []
            for row in cursor.fetchall():
                message = {
                    "role": row[0],
                    "content": row[1],
                    "timestamp": row[3]
                }
                if row[2]:
                    try:
                        message["metadata"] = json.loads(row[2])
                    except json.JSONDecodeError:
                        pass
                messages.append(message)
            
            # 反转顺序（从旧到新）
            messages.reverse()
            return messages
    
    def get_history_for_llm(self, session_id: str, max_rounds: int = 15) -> List[Dict[str, str]]:
        """
        获取适合LLM的历史记录
        
        Args:
            session_id: 会话ID
            max_rounds: 最大轮数
            
        Returns:
            LLM格式的消息列表
        """
        messages = self.get_messages(session_id, limit=max_rounds * 2)
        
        # 转换为LLM格式
        llm_messages = []
        for msg in messages:
            if msg["role"] in ["system", "user", "assistant"]:
                llm_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        return llm_messages
    
    def clear_conversation(self, session_id: str):
        """
        清除对话历史
        
        Args:
            session_id: 会话ID
        """
        with sqlite3.connect(self.db_path) as conn:
            # 获取对话ID
            cursor = conn.execute(
                "SELECT id FROM conversations WHERE session_id = ?",
                (session_id,)
            )
            rows = cursor.fetchall()
            
            for row in rows:
                conversation_id = row[0]
                conn.execute(
                    "DELETE FROM messages WHERE conversation_id = ?",
                    (conversation_id,)
                )
            
            conn.execute(
                "DELETE FROM conversations WHERE session_id = ?",
                (session_id,)
            )
            
            conn.commit()
    
    def get_conversation_stats(self, session_id: str) -> Dict[str, Any]:
        """
        获取对话统计信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            统计信息
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT COUNT(*) as message_count,
                          MIN(timestamp) as first_message,
                          MAX(timestamp) as last_message
                   FROM messages m
                   JOIN conversations c ON m.conversation_id = c.id
                   WHERE c.session_id = ?""",
                (session_id,)
            )
            
            row = cursor.fetchone()
            if row:
                return {
                    "message_count": row[0],
                    "first_message": row[1],
                    "last_message": row[2]
                }
            
            return {"message_count": 0}
    
    def list_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        列出所有对话
        
        Args:
            limit: 限制数量
            
        Returns:
            对话列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute(
                """SELECT c.session_id, c.created_at, c.updated_at,
                          COUNT(m.id) as message_count
                   FROM conversations c
                   LEFT JOIN messages m ON c.id = m.conversation_id
                   GROUP BY c.id
                   ORDER BY c.updated_at DESC
                   LIMIT ?""",
                (limit,)
            )
            
            conversations = []
            for row in cursor.fetchall():
                conversations.append({
                    "session_id": row[0],
                    "created_at": row[1],
                    "updated_at": row[2],
                    "message_count": row[3]
                })
            
            return conversations


# 全局单例
_memory_instance: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """获取全局对话记忆实例"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ConversationMemory()
    return _memory_instance

"""护栏决策存储管理器 - 支持安全护栏决策持久化"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


class GateStorage:
    """护栏决策存储管理器，支持SQLite持久化存储"""
    
    def __init__(self, db_path: str = "data/gate_decisions.db"):
        """
        初始化护栏决策存储管理器
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            # 护栏决策表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gate_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT UNIQUE NOT NULL,
                    trace_id TEXT,
                    user_message TEXT,
                    command TEXT,
                    tool_name TEXT,
                    risk_level TEXT,
                    verdict TEXT,
                    allowed BOOLEAN,
                    reason TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gate_decisions_trace_id 
                ON gate_decisions(trace_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gate_decisions_created_at 
                ON gate_decisions(created_at)
            """)
            
            conn.commit()
    
    def save_decision(self, decision_id: str, trace_id: str = None,
                     user_message: str = None, command: str = None,
                     tool_name: str = None, risk_level: str = None,
                     verdict: str = None, allowed: bool = True,
                     reason: str = None, metadata: Dict[str, Any] = None) -> int:
        """
        保存护栏决策
        """
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT OR REPLACE INTO gate_decisions 
                   (decision_id, trace_id, user_message, command, tool_name, 
                    risk_level, verdict, allowed, reason, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (decision_id, trace_id, user_message, command, tool_name,
                 risk_level, verdict, allowed, reason, metadata_json)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """获取决策信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute(
                "SELECT * FROM gate_decisions WHERE decision_id = ?",
                (decision_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                return None
            
            decision = {
                "decision_id": row[1],
                "trace_id": row[2],
                "user_message": row[3],
                "command": row[4],
                "tool_name": row[5],
                "risk_level": row[6],
                "verdict": row[7],
                "allowed": bool(row[8]),
                "reason": row[9],
                "metadata": json.loads(row[10]) if row[10] else None,
                "created_at": row[11]
            }
            
            return decision
    
    def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            # 总决策数
            cursor = conn.execute("SELECT COUNT(*) FROM gate_decisions")
            total_decisions = cursor.fetchone()[0]
            
            # 允许的决策数
            cursor = conn.execute("SELECT COUNT(*) FROM gate_decisions WHERE allowed = 1")
            allowed_decisions = cursor.fetchone()[0]
            
            # 拒绝的决策数
            cursor = conn.execute("SELECT COUNT(*) FROM gate_decisions WHERE allowed = 0")
            blocked_decisions = cursor.fetchone()[0]
            
            # 风险等级统计
            cursor = conn.execute(
                "SELECT risk_level, COUNT(*) FROM gate_decisions GROUP BY risk_level"
            )
            risk_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_decisions": total_decisions,
                "allowed_decisions": allowed_decisions,
                "blocked_decisions": blocked_decisions,
                "risk_stats": risk_stats,
                "block_rate": round(blocked_decisions / total_decisions * 100, 2) if total_decisions > 0 else 0
            }


# 全局单例
_gate_storage_instance: Optional[GateStorage] = None


def get_gate_storage() -> GateStorage:
    """获取全局护栏决策存储实例"""
    global _gate_storage_instance
    if _gate_storage_instance is None:
        _gate_storage_instance = GateStorage()
    return _gate_storage_instance

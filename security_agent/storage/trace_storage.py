"""追踪存储管理器 - 支持TraceContext持久化"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


class TraceStorage:
    """追踪存储管理器，支持SQLite持久化存储"""
    
    def __init__(self, db_path: str = "data/traces.db"):
        """
        初始化追踪存储管理器
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            # 追踪表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT UNIQUE NOT NULL,
                    user_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT DEFAULT 'running',
                    metadata TEXT
                )
            """)
            
            # 阶段表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trace_stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    stage_data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    duration_ms INTEGER,
                    FOREIGN KEY (trace_id) REFERENCES traces(trace_id)
                )
            """)
            
            # 索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_traces_trace_id 
                ON traces(trace_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trace_stages_trace_id 
                ON trace_stages(trace_id)
            """)
            
            conn.commit()
    
    def create_trace(self, trace_id: str, user_message: str = None, 
                     metadata: Dict[str, Any] = None) -> int:
        """
        创建新追踪
        
        Args:
            trace_id: 追踪ID
            user_message: 用户消息
            metadata: 元数据
            
        Returns:
            追踪ID
        """
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        
        from security_agent.timeutil import now_iso

        created = now_iso()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT OR REPLACE INTO traces (trace_id, user_message, metadata, created_at) 
                   VALUES (?, ?, ?, ?)""",
                (trace_id, user_message, metadata_json, created),
            )
            conn.commit()
            return cursor.lastrowid
    
    def add_stage(
        self,
        trace_id: str,
        stage_name: str,
        stage_data: Dict[str, Any] = None,
        duration_ms: int = None,
        *,
        timestamp: str | None = None,
    ) -> int:
        """
        添加追踪阶段
        
        Args:
            trace_id: 追踪ID
            stage_name: 阶段名称
            stage_data: 阶段数据
            duration_ms: 持续时间（毫秒）
            
        Returns:
            阶段ID
        """
        from security_agent.timeutil import now_iso

        stage_data_json = json.dumps(stage_data, ensure_ascii=False) if stage_data else None
        ts = timestamp or now_iso()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO trace_stages (trace_id, stage_name, stage_data, duration_ms, timestamp) 
                   VALUES (?, ?, ?, ?, ?)""",
                (trace_id, stage_name, stage_data_json, duration_ms, ts),
            )
            conn.commit()
            return cursor.lastrowid
    
    def complete_trace(self, trace_id: str, status: str = "completed"):
        """
        完成追踪
        
        Args:
            trace_id: 追踪ID
            status: 状态
        """
        from security_agent.timeutil import now_iso

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE traces 
                   SET completed_at = ?, status = ? 
                   WHERE trace_id = ?""",
                (now_iso(), status, trace_id),
            )
            conn.commit()
    
    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        获取追踪信息
        
        Args:
            trace_id: 追踪ID
            
        Returns:
            追踪信息
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # 获取追踪基本信息
            cursor = conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?",
                (trace_id,)
            )
            trace_row = cursor.fetchone()
            
            if not trace_row:
                return None
            
            trace_info = {
                "trace_id": trace_row[1],
                "user_message": trace_row[2],
                "created_at": trace_row[3],
                "completed_at": trace_row[4],
                "status": trace_row[5],
                "metadata": json.loads(trace_row[6]) if trace_row[6] else None,
                "stages": []
            }
            
            # 获取阶段信息
            cursor = conn.execute(
                """SELECT stage_name, stage_data, timestamp, duration_ms 
                   FROM trace_stages 
                   WHERE trace_id = ? 
                   ORDER BY id""",
                (trace_id,)
            )
            
            for row in cursor.fetchall():
                stage = {
                    "name": row[0],
                    "data": json.loads(row[1]) if row[1] else None,
                    "timestamp": row[2],
                    "duration_ms": row[3]
                }
                trace_info["stages"].append(stage)
            
            return trace_info
    
    def list_traces(self, limit: int = 50, status: str = None) -> List[Dict[str, Any]]:
        """
        列出追踪
        
        Args:
            limit: 限制数量
            status: 状态过滤
            
        Returns:
            追踪列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM traces"
            params = []
            
            if status:
                query += " WHERE status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            
            traces = []
            for row in cursor.fetchall():
                trace = {
                    "trace_id": row[1],
                    "user_message": row[2],
                    "created_at": row[3],
                    "completed_at": row[4],
                    "status": row[5],
                    "metadata": json.loads(row[6]) if row[6] else None
                }
                traces.append(trace)
            
            return traces

    def list_traces_summary(self, limit: int = 50, status: str | None = None) -> List[Dict[str, Any]]:
        """列出追踪并附带阶段数/阶段耗时合计（L4/L5 共享）."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = """
                SELECT t.trace_id, t.user_message, t.created_at, t.completed_at, t.status, t.metadata,
                       COUNT(s.id) AS stage_count,
                       COALESCE(SUM(s.duration_ms), 0) AS stage_ms
                FROM traces t
                LEFT JOIN trace_stages s ON t.trace_id = s.trace_id
            """
            params: list[Any] = []
            if status:
                query += " WHERE t.status = ?"
                params.append(status)
            query += " GROUP BY t.trace_id ORDER BY t.created_at DESC LIMIT ?"
            params.append(limit)
            cursor = conn.execute(query, params)
            traces: list[dict[str, Any]] = []
            for row in cursor.fetchall():
                traces.append({
                    "trace_id": row["trace_id"],
                    "user_message": row["user_message"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                    "status": row["status"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
                    "stage_count": int(row["stage_count"] or 0),
                    "stage_ms": float(row["stage_ms"] or 0),
                })
            return traces
    
    def get_trace_stats(self) -> Dict[str, Any]:
        """
        获取追踪统计信息
        
        Returns:
            统计信息
        """
        with sqlite3.connect(self.db_path) as conn:
            # 总追踪数
            cursor = conn.execute("SELECT COUNT(*) FROM traces")
            total_traces = cursor.fetchone()[0]
            
            # 按状态统计
            cursor = conn.execute(
                "SELECT status, COUNT(*) FROM traces GROUP BY status"
            )
            status_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 平均阶段数
            cursor = conn.execute(
                """SELECT AVG(stage_count) FROM 
                   (SELECT COUNT(*) as stage_count FROM trace_stages GROUP BY trace_id)"""
            )
            avg_stages = cursor.fetchone()[0] or 0
            
            return {
                "total_traces": total_traces,
                "status_stats": status_stats,
                "average_stages_per_trace": round(avg_stages, 2)
            }
    
    def delete_trace(self, trace_id: str) -> bool:
        """删除单条 trace."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM trace_stages WHERE trace_id = ?", (trace_id,))
            conn.execute("DELETE FROM traces WHERE trace_id = ?", (trace_id,))
            conn.commit()
            return True

    def cleanup_old_traces(self, days: int = 30) -> int:
        """清理旧追踪，返回删除数."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """DELETE FROM trace_stages
                   WHERE trace_id IN (
                       SELECT trace_id FROM traces
                       WHERE created_at < datetime('now', ?)
                   )""",
                (f'-{days} days',)
            )
            cur = conn.execute(
                "DELETE FROM traces WHERE created_at < datetime('now', ?)",
                (f'-{days} days',)
            )
            conn.commit()
            return cur.rowcount


# 全局单例
_storage_instance: Optional[TraceStorage] = None


def get_trace_storage() -> TraceStorage:
    """获取全局追踪存储实例"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = TraceStorage()
    return _storage_instance

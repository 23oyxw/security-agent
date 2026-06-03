"""统一数据库管理器 - 合并所有SQLite连接"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator, Optional
from pathlib import Path


class DatabaseManager:
    """统一数据库管理器 - 单例模式，管理所有数据库连接"""
    
    _instance: Optional[DatabaseManager] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._connections = {}
            self._connection_lock = threading.Lock()
            self._db_dir = Path("data")
            self._db_dir.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self, db_name: str = "main.db") -> sqlite3.Connection:
        """获取数据库连接（线程安全）"""
        with self._connection_lock:
            if db_name not in self._connections:
                db_path = self._db_dir / db_name
                conn = sqlite3.connect(str(db_path), check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")  # 提高并发性能
                conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全
                conn.execute("PRAGMA cache_size=-64000")  # 64MB缓存
                self._connections[db_name] = conn
            return self._connections[db_name]
    
    @contextmanager
    def get_cursor(self, db_name: str = "main.db") -> Generator[sqlite3.Cursor, None, None]:
        """获取数据库游标（上下文管理器）"""
        conn = self.get_connection(db_name)
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def execute_query(self, query: str, params: tuple = (), 
                     db_name: str = "main.db") -> list:
        """执行查询语句"""
        with self.get_cursor(db_name) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = (), 
                      db_name: str = "main.db") -> int:
        """执行更新语句"""
        with self.get_cursor(db_name) as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: list, 
                    db_name: str = "main.db") -> int:
        """批量执行更新语句"""
        with self.get_cursor(db_name) as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def create_table(self, table_name: str, schema: str, 
                    db_name: str = "main.db") -> bool:
        """创建表"""
        try:
            with self.get_cursor(db_name) as cursor:
                # schema应该包含括号，如: (id INTEGER PRIMARY KEY, name TEXT)
                if not schema.strip().startswith('('):
                    schema = f"({schema})"
                cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} {schema}")
            return True
        except Exception as e:
            print(f"创建表失败: {e}")
            return False
    
    def table_exists(self, table_name: str, db_name: str = "main.db") -> bool:
        """检查表是否存在"""
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.execute_query(query, (table_name,), db_name)
        return len(result) > 0
    
    def get_table_count(self, table_name: str, db_name: str = "main.db") -> int:
        """获取表记录数"""
        query = f"SELECT COUNT(*) FROM {table_name}"
        result = self.execute_query(query, db_name=db_name)
        return result[0][0] if result else 0
    
    def close_all(self):
        """关闭所有连接"""
        with self._connection_lock:
            for db_name, conn in self._connections.items():
                try:
                    conn.close()
                except Exception as e:
                    print(f"关闭数据库连接失败 {db_name}: {e}")
            self._connections.clear()
    
    def __del__(self):
        """析构函数"""
        self.close_all()


# 全局单例
def get_database_manager() -> DatabaseManager:
    """获取全局数据库管理器实例"""
    return DatabaseManager()

"""用户存储 — SQLite · 龙架构兼容（passlib pbkdf2，无需 bcrypt C 扩展）"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional, List

from passlib.hash import pbkdf2_sha256

from security_agent import config
from security_agent.auth.models import User


class UserStore:
    """SQLite 用户存储"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (config.DATA_DIR / "auth.db")
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    hashed_password TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    display_name TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    disabled INTEGER DEFAULT 0,
                    created_at REAL,
                    last_login REAL
                )
            """)
            conn.commit()

    def _row_to_user(self, row: tuple) -> User:
        return User(
            username=row[0],
            hashed_password=row[1],
            role=row[2],
            display_name=row[3],
            email=row[4],
            disabled=bool(row[5]),
            created_at=row[6] or 0,
            last_login=row[7],
        )

    def get_user(self, username: str) -> Optional[User]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            )
            row = cursor.fetchone()
            return self._row_to_user(row) if row else None

    def list_users(self) -> List[User]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [self._row_to_user(row) for row in cursor.fetchall()]

    def create_user(self, username: str, password: str, role: str = "viewer",
                    display_name: str = "", email: str = "") -> User:
        hashed = pbkdf2_sha256.hash(password)
        now = time.time()
        user = User(
            username=username,
            hashed_password=hashed,
            role=role,
            display_name=display_name or username,
            email=email,
            created_at=now,
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO users
                   (username, hashed_password, role, display_name, email, disabled, created_at)
                   VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (username, hashed, role, display_name or username, email, now),
            )
            conn.commit()
        return user

    def verify_password(self, username: str, password: str) -> bool:
        user = self.get_user(username)
        if not user or user.disabled:
            return False
        try:
            return pbkdf2_sha256.verify(password, user.hashed_password)
        except Exception:
            return False

    def update_last_login(self, username: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE username = ?",
                (time.time(), username),
            )
            conn.commit()

    def delete_user(self, username: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            return cursor.rowcount > 0


# 全局单例
_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store

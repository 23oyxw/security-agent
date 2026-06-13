"""分析计划持久化 — 运维可复盘、执行可重试."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

_DB = Path("data/plans.db")


class PlanStore:
    def __init__(self, db_path: str | Path = _DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    batch_id TEXT,
                    status TEXT NOT NULL,
                    phase TEXT,
                    plan_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_plans_trace ON plans(trace_id)"
            )
            conn.commit()

    def save(self, plan: dict[str, Any]) -> None:
        pid = plan["plan_id"]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO plans (plan_id, trace_id, batch_id, status, phase, plan_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id) DO UPDATE SET
                    trace_id=excluded.trace_id,
                    batch_id=excluded.batch_id,
                    status=excluded.status,
                    phase=excluded.phase,
                    plan_json=excluded.plan_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    pid,
                    plan.get("trace_id") or "",
                    plan.get("batch_id"),
                    plan.get("status") or "planned",
                    plan.get("phase"),
                    json.dumps(plan, ensure_ascii=False),
                ),
            )
            conn.commit()

    def get(self, plan_id: str) -> Optional[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT plan_json FROM plans WHERE plan_id = ?", (plan_id,)
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def get_by_trace(self, trace_id: str) -> Optional[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT plan_json FROM plans WHERE trace_id = ? ORDER BY updated_at DESC LIMIT 1",
                (trace_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT plan_json FROM plans ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(json.loads(row[0]))
            except json.JSONDecodeError:
                continue
        return out


_default_store: PlanStore | None = None


def get_plan_store() -> PlanStore:
    global _default_store
    if _default_store is None:
        _default_store = PlanStore()
    return _default_store

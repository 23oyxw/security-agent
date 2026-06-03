"""用户确认流程管理器 - 支持风险操作的用户确认"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ConfirmationStatus(str, Enum):
    """确认状态"""
    PENDING = "pending"           # 等待确认
    APPROVED = "approved"         # 已批准
    REJECTED = "rejected"         # 已拒绝
    TIMEOUT = "timeout"          # 超时
    CANCELLED = "cancelled"       # 已取消


class ConfirmationLevel(str, Enum):
    """确认级别"""
    AUTO = "auto"                # 自动放行
    CONFIRM = "confirm"          # 需要确认
    APPROVE = "approve"          # 需要审批
    ESCALATE = "escalate"        # 升级审批


@dataclass
class ConfirmationRequest:
    """确认请求"""
    request_id: str
    trace_id: str
    user_message: str
    action_description: str
    risk_level: str
    confirmation_level: ConfirmationLevel
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    requested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    responded_at: Optional[str] = None
    responder: Optional[str] = None
    response_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "user_message": self.user_message,
            "action_description": self.action_description,
            "risk_level": self.risk_level,
            "confirmation_level": self.confirmation_level.value,
            "status": self.status.value,
            "requested_at": self.requested_at,
            "responded_at": self.responded_at,
            "responder": self.responder,
            "response_reason": self.response_reason,
            "metadata": self.metadata
        }


class ConfirmationManager:
    """用户确认流程管理器"""
    
    def __init__(self, db_path: str = "data/confirmations.db"):
        """
        初始化确认管理器
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._pending_requests: Dict[str, ConfirmationRequest] = {}
        self._reload_pending_cache()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            # 确认请求表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS confirmation_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT UNIQUE NOT NULL,
                    trace_id TEXT,
                    user_message TEXT,
                    action_description TEXT,
                    risk_level TEXT,
                    confirmation_level TEXT,
                    status TEXT DEFAULT 'pending',
                    requested_at TIMESTAMP,
                    responded_at TIMESTAMP,
                    responder TEXT,
                    response_reason TEXT,
                    metadata TEXT
                )
            """)
            
            # 索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_trace_id 
                ON confirmation_requests(trace_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_status 
                ON confirmation_requests(status)
            """)
            
            conn.commit()
    
    def create_request(self, trace_id: str, user_message: str,
                      action_description: str, risk_level: str,
                      confirmation_level: ConfirmationLevel,
                      metadata: Dict[str, Any] = None) -> ConfirmationRequest:
        """
        创建确认请求
        
        Args:
            trace_id: 追踪ID
            user_message: 用户消息
            action_description: 动作描述
            risk_level: 风险等级
            confirmation_level: 确认级别
            metadata: 元数据
            
        Returns:
            确认请求
        """
        request_id = f"confirm_{uuid.uuid4().hex[:8]}"
        
        from security_agent import config

        meta = dict(metadata or {})
        if "expires_at" not in meta:
            expires = datetime.now() + timedelta(seconds=config.CONFIRMATION_TIMEOUT_SEC)
            meta["expires_at"] = expires.isoformat()

        request = ConfirmationRequest(
            request_id=request_id,
            trace_id=trace_id,
            user_message=user_message,
            action_description=action_description,
            risk_level=risk_level,
            confirmation_level=confirmation_level,
            metadata=meta,
        )
        
        # 保存到数据库
        self._save_request(request)
        
        # 添加到待处理列表
        self._pending_requests[request_id] = request
        
        return request
    
    def _save_request(self, request: ConfirmationRequest):
        """保存请求到数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO confirmation_requests 
                   (request_id, trace_id, user_message, action_description, 
                    risk_level, confirmation_level, status, requested_at, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (request.request_id, request.trace_id, request.user_message,
                 request.action_description, request.risk_level,
                 request.confirmation_level.value, request.status.value,
                 request.requested_at, json.dumps(request.metadata))
            )
            conn.commit()
    
    def approve_request(self, request_id: str, responder: str = "user",
                       reason: str = None) -> bool:
        """
        批准请求
        
        Args:
            request_id: 请求ID
            responder: 响应者
            reason: 原因
            
        Returns:
            是否成功
        """
        return self._update_request_status(
            request_id, ConfirmationStatus.APPROVED, responder, reason
        )
    
    def reject_request(self, request_id: str, responder: str = "user",
                      reason: str = None) -> bool:
        """
        拒绝请求
        
        Args:
            request_id: 请求ID
            responder: 响应者
            reason: 原因
            
        Returns:
            是否成功
        """
        return self._update_request_status(
            request_id, ConfirmationStatus.REJECTED, responder, reason
        )
    
    def _update_request_status(self, request_id: str, status: ConfirmationStatus,
                              responder: str, reason: str) -> bool:
        """更新请求状态"""
        responded_at = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE confirmation_requests 
                   SET status = ?, responded_at = ?, responder = ?, response_reason = ?
                   WHERE request_id = ?""",
                (status.value, responded_at, responder, reason, request_id)
            )
            conn.commit()
        
        # 更新内存中的请求
        if request_id in self._pending_requests:
            request = self._pending_requests[request_id]
            request.status = status
            request.responded_at = responded_at
            request.responder = responder
            request.response_reason = reason
            
            # 如果不是待处理状态，从待处理列表中移除
            if status != ConfirmationStatus.PENDING:
                del self._pending_requests[request_id]
        
        return True
    
    def get_request(self, request_id: str) -> Optional[ConfirmationRequest]:
        """获取请求"""
        # 先从内存中查找
        if request_id in self._pending_requests:
            return self._pending_requests[request_id]
        
        # 从数据库中查找
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM confirmation_requests WHERE request_id = ?",
                (request_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            return self._row_to_request(row)
    
    def _reload_pending_cache(self) -> None:
        """启动时从 DB 恢复 pending 队列."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM confirmation_requests WHERE status = ? ORDER BY requested_at",
                (ConfirmationStatus.PENDING.value,),
            )
            for row in cursor.fetchall():
                req = self._row_to_request(row)
                self._pending_requests[req.request_id] = req

    @staticmethod
    def _row_to_request(row: sqlite3.Row) -> ConfirmationRequest:
        return ConfirmationRequest(
            request_id=row[1],
            trace_id=row[2],
            user_message=row[3],
            action_description=row[4],
            risk_level=row[5],
            confirmation_level=ConfirmationLevel(row[6]),
            status=ConfirmationStatus(row[7]),
            requested_at=row[8],
            responded_at=row[9],
            responder=row[10],
            response_reason=row[11],
            metadata=json.loads(row[12]) if row[12] else {},
        )

    def expire_stale_requests(self) -> int:
        """将超时 pending 标记为 timeout（企业级 S4 兜底）."""
        from security_agent.audit import log as audit
        from security_agent import config

        expired = 0
        now = datetime.now()
        limit = timedelta(seconds=config.CONFIRMATION_TIMEOUT_SEC)
        pending = self.list_pending_requests(refresh=True)
        for req in pending:
            try:
                requested = datetime.fromisoformat(req.requested_at)
            except ValueError:
                continue
            if now - requested <= limit:
                continue
            self._update_request_status(
                req.request_id,
                ConfirmationStatus.TIMEOUT,
                "system",
                f"审批超时（>{config.CONFIRMATION_TIMEOUT_SEC}s）",
            )
            audit.append_audit(
                "approval_timeout",
                {"request_id": req.request_id, "trace_id": req.trace_id},
                level="warning",
            )
            expired += 1
        return expired

    def list_pending_requests(self, refresh: bool = False) -> List[ConfirmationRequest]:
        """列出待处理请求（可选从 DB 刷新）."""
        if refresh:
            self._pending_requests.clear()
            self._reload_pending_cache()
        return list(self._pending_requests.values())
    
    def get_requests_by_trace(self, trace_id: str) -> List[ConfirmationRequest]:
        """获取追踪的所有请求"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT * FROM confirmation_requests 
                   WHERE trace_id = ? 
                   ORDER BY requested_at""",
                (trace_id,)
            )
            
            requests = []
            for row in cursor.fetchall():
                request = ConfirmationRequest(
                    request_id=row[1],
                    trace_id=row[2],
                    user_message=row[3],
                    action_description=row[4],
                    risk_level=row[5],
                    confirmation_level=ConfirmationLevel(row[6]),
                    status=ConfirmationStatus(row[7]),
                    requested_at=row[8],
                    responded_at=row[9],
                    responder=row[10],
                    response_reason=row[11],
                    metadata=json.loads(row[12]) if row[12] else {}
                )
                requests.append(request)
            
            return requests
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            # 总请求数
            cursor = conn.execute("SELECT COUNT(*) FROM confirmation_requests")
            total_requests = cursor.fetchone()[0]
            
            # 按状态统计
            cursor = conn.execute(
                "SELECT status, COUNT(*) FROM confirmation_requests GROUP BY status"
            )
            status_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 按确认级别统计
            cursor = conn.execute(
                "SELECT confirmation_level, COUNT(*) FROM confirmation_requests GROUP BY confirmation_level"
            )
            level_stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_requests": total_requests,
                "status_stats": status_stats,
                "level_stats": level_stats,
                "pending_count": len(self._pending_requests)
            }


# 全局单例
_confirmation_manager_instance: Optional[ConfirmationManager] = None


def get_confirmation_manager() -> ConfirmationManager:
    """获取全局确认管理器实例"""
    global _confirmation_manager_instance
    if _confirmation_manager_instance is None:
        _confirmation_manager_instance = ConfirmationManager()
    return _confirmation_manager_instance

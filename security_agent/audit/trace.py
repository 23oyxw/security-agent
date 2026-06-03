"""统一 TraceContext — 用 contextvars 在单次请求中自动传递 trace_id.

用法:
    from security_agent.audit.trace import TraceContext

    with TraceContext() as ctx:
        # 所有模块通过 ctx.get_trace_id() 获取统一的 trace_id
        do_step("感知环境")
        do_step("推理决策")
        do_step("安全校验")
        do_step("执行结果")
"""

from __future__ import annotations

import contextvars
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from security_agent.audit import log as audit
from security_agent.timeutil import now_iso
from security_agent.storage import get_trace_storage

_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
_trace_started_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_started_at", default="")

# 推理链路各阶段记录
TRACE_STAGES = (
    "receive_request",       # 接收指令
    "environment_probe",     # 感知环境
    "inference_decision",    # 推理决策
    "safety_check",          # 安全校验
    "execution",             # 执行结果
    "post_verify",           # 执行后验证
)


class TraceContext:
    """全链路追踪上下文管理器.

    自动为当前请求生成 trace_id，并通过 contextvars 传递给所有下游模块。
    退出时自动写入 TTL 结束日志。

    用法:
        ctx = TraceContext(user_message="帮我清理系统垃圾")
        with ctx:
            ctx.stage("environment_probe", {"disk_usage": "85%"})
            ctx.stage("inference_decision", {"plan": "清理 /var/log 大文件"})
            ctx.stage("safety_check", {"verdict": "confirm"})
            ctx.stage("execution", {"command": "du -sh /var/log/*"})
    """

    def __init__(
        self,
        *,
        trace_id: str = "",
        user_message: str = "",
        user: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        self._trace_id = trace_id or f"trace-{uuid.uuid4().hex[:12]}"
        self._started_at = now_iso()
        self._user_message = user_message
        self._user = user
        self._metadata = metadata or {}
        self._stages: list[dict[str, Any]] = []
        self._token: contextvars.Token[str] | None = None
        self._started_token: contextvars.Token[str] | None = None
        self._stage_perf_origin = time.perf_counter()
        self._last_stage_cumulative_ms = 0

        # 持久化存储
        self.storage = get_trace_storage()
        self._save_to_storage()

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def started_at(self) -> str:
        return self._started_at

    def _save_to_storage(self) -> None:
        """保存到存储"""
        try:
            if self.storage:
                self.storage.create_trace(
                    self._trace_id,
                    self._user_message,
                    {"started_at": self._started_at}
                )
        except Exception as e:
            print(f"保存追踪到存储失败: {e}")
    
    def __enter__(self) -> TraceContext:
        self._token = _trace_id_var.set(self._trace_id)
        self._started_token = _trace_started_var.set(self._started_at)
        audit.append_audit(
            "trace_begin",
            {
                "trace_id": self._trace_id,
                "user_message": self._user_message[:500],
                "user": self._user,
                "metadata": self._metadata,
            },
            level="info",
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            _trace_id_var.reset(self._token)
            self._token = None
        if self._started_token is not None:
            _trace_started_var.reset(self._started_token)
            self._started_token = None

        end_at = now_iso()
        duration_ms = 0.0
        try:
            start_dt = datetime.fromisoformat(self._started_at)
            end_dt = datetime.fromisoformat(end_at)
            duration_ms = (end_dt - start_dt).total_seconds() * 1000
        except (ValueError, TypeError):
            pass

        audit.append_audit(
            "trace_end",
            {
                "trace_id": self._trace_id,
                "stages": self._stages,
                "total_stages": len(self._stages),
                "error": str(exc_val) if exc_val else None,
                "duration_ms": round(duration_ms, 2),
            },
            level="error" if exc_val else "info",
        )

    
    def complete_trace(self, status: str = "completed") -> None:
        """完成追踪"""
        try:
            if self.storage:
                self.storage.complete_trace(self.trace_id, status)
        except Exception as e:
            print(f"完成追踪失败: {e}")
    
    def get_trace_info(self) -> dict:
        """获取追踪信息"""
        try:
            if self.storage:
                return self.storage.get_trace(self.trace_id)
        except Exception as e:
            print(f"获取追踪信息失败: {e}")
        return None
    def stage(self, name: str, detail: dict[str, Any] | None = None) -> None:
        """记录推理链路的一个阶段。

        Args:
            name: 阶段名，应在 TRACE_STAGES 中定义
            detail: 该阶段的详细信息（决策、结果等）
        """
        stage_entry = {
            "stage": name,
            "ts": now_iso(),
            "trace_id": self._trace_id,
            "detail": detail or {},
        }
        self._stages.append(stage_entry)
        audit.append_audit(
            f"trace_stage:{name}",
            stage_entry,
            level="info",
        )
        
        # 保存到存储（单阶段耗时 = 距上一阶段的增量，时间戳统一北京时间 ISO）
        try:
            if hasattr(self, "storage") and self.storage:
                cumulative_ms = int((time.perf_counter() - self._stage_perf_origin) * 1000)
                delta_ms = max(0, cumulative_ms - self._last_stage_cumulative_ms)
                self._last_stage_cumulative_ms = cumulative_ms
                self.storage.add_stage(
                    self._trace_id,
                    name,
                    detail,
                    delta_ms,
                    timestamp=now_iso(),
                )
        except Exception as e:
            print(f"保存阶段到存储失败: {e}")

    def stage_environment(self, snapshot: dict[str, Any]) -> None:
        """快捷方法：记录环境感知阶段."""
        self.stage("environment_probe", snapshot)

    def stage_inference(self, plan: dict[str, Any]) -> None:
        """快捷方法：记录推理决策阶段."""
        self.stage("inference_decision", plan)

    def stage_safety(self, verdict: str, reason: str, **extra: Any) -> None:
        """快捷方法：记录安全校验阶段."""
        self.stage("safety_check", {"verdict": verdict, "reason": reason, **extra})

    def stage_execution(self, command: str, exit_code: int, **extra: Any) -> None:
        """快捷方法：记录执行结果阶段."""
        self.stage("execution", {"command": command, "exit_code": exit_code, **extra})

    def to_summary(self) -> dict[str, Any]:
        """生成链路摘要（供 UI / 报告使用）."""
        return {
            "trace_id": self._trace_id,
            "started_at": self._started_at,
            "user_message": self._user_message,
            "user": self._user,
            "stages": [s["stage"] for s in self._stages],
            "stage_count": len(self._stages),
        }

    # ---- 静态方法：在不持有上下文时读取当前 trace_id ----

    @staticmethod
    def current_trace_id() -> str:
        """获取当前协程/线程的 trace_id，若无则返回空字符串."""
        return _trace_id_var.get()

    @staticmethod
    def current_trace_started_at() -> str:
        """获取当前协程/线程的 trace 开始时间."""
        return _trace_started_var.get()

    @staticmethod
    @contextmanager
    def set_temp_trace_id(trace_id: str):
        """临时设置一个 trace_id，退出时恢复原值。用于异步任务派生。"""
        token = _trace_id_var.set(trace_id)
        try:
            yield
        finally:
            _trace_id_var.reset(token)
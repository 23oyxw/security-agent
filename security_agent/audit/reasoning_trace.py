"""推理链路全链路追溯系统 — 生产级可观测性核心.

赛题要求: 推理链路可追溯性
  - 技术价值: 解决故障定位难、结果可信度低问题
  - 符合生产级 Agent 可观测刚需

能力覆盖:
  1. 推理全过程记录：保存思考逻辑、工具参数、执行结果
  2. 结果来源可溯源：关联原始文档/工具ID/操作记录/审计日志
  3. 异常可排查：提供全链路 Trace ID 追踪能力，支持快速定位
  4. 推理决策树可视化输出（JSON 格式）

数据模型:
  ┌─────────────────────────────────────────────┐
  │              ReasoningTrace                  │
  │                                              │
  │  trace_id: "trace-abc123def456"             │
  │  session_id: "sess-xxx"                      │
  │  user_message: "CPU使用率异常"               │
  │  strategy: "react"                           │
  │  status: "completed"                         │
  │                                              │
  │  thoughts: [...]        ← Agent 思考过程    │
  │  actions: [...]         ← 工具调用记录      │
  │  observations: [...]     ← 观察结果          │
  │  safety_checks: [...]    ← 安全校验记录      │
  │  knowledge_refs: [...]   ← 知识库引用        │
  │  errors: [...]           ← 异常记录          │
  └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
)
import contextvars

logger = logging.getLogger(__name__)

# 推理追溯持久化根目录
_TRACE_DIR: Optional[Path] = None


def _get_trace_dir() -> Path:
    """获取/初始化 trace 持久化目录."""
    global _TRACE_DIR
    if _TRACE_DIR is None:
        from security_agent import config
        _TRACE_DIR = config.DATA_DIR / "traces"
    _TRACE_DIR.mkdir(parents=True, exist_ok=True)
    return _TRACE_DIR

# =============================================================================
# 全局 ContextVar — 跨模块自动传递 trace_id
# =============================================================================

_current_trace_var: contextvars.ContextVar[Optional[ReasoningTrace]] = contextvars.ContextVar(
    "_current_trace", default=None,
)


# =============================================================================
# 枚举定义
# =============================================================================


class TraceStatus(str, Enum):
    """追踪状态."""
    CREATED = "created"
    PERCEIVING = "perceiving"                    # 感知阶段
    REASONING = "reasoning"                      # 推理阶段
    SAFETY_CHECK = "safety_check"                # 安全校验
    EXECUTING = "executing"                      # 执行阶段
    VERIFYING = "verifying"                      # 验证阶段
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"                 # 断点续跑
    ROLLED_BACK = "rolled_back"                  # 已回滚


class ThoughtType(str, Enum):
    """思考类型."""
    OBSERVATION = "observation"                  # 观察/感知结论
    HYPOTHESIS = "hypothesis"                     # 假设形成
    REASONING = "reasoning"                       # 推理步骤
    PLANNING = "planning"                          # 计划制定
    REFLECTION = "reflection"                      # 反思修正
    DECISION = "decision"                          # 最终决策
    UNCERTAINTY = "uncertainty"                   # 不确定性声明


class ActionPhase(str, Enum):
    """操作阶段."""
    PRE_EXECUTION = "pre_execution"              # 执行前
    EXECUTING = "executing"                       # 执行中
    POST_EXECUTION = "post_execution"            # 执行后


# =============================================================================
# 数据模型
# =============================================================================


@dataclass
class ThoughtRecord:
    """思考记录 — 记录 Agent 的每一步推理."""
    step_number: int                             # 步骤序号
    timestamp: str                               # 时间戳
    thought_type: ThoughtType                    # 思考类型
    content: str                                 # 思考内容
    confidence: float = 0.8                      # 置信度 (0-1)
    source_tool_ids: List[str] = field(default_factory=list)   # 关联的工具ID
    source_knowledge_ids: List[str] = field(default_factory=list)  # 引用的知识条目ID
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["thought_type"] = self.thought_type.value
        return d


@dataclass
class ActionRecord:
    """操作记录 — 记录每次工具调用."""
    action_number: int                           # 操作序号
    timestamp: str
    phase: ActionPhase                           # 操作阶段
    tool_name: str                                # 工具名称
    tool_id: str                                  # 全局唯一工具ID
    arguments: Dict[str, Any]                    # 调用参数
    result_summary: str = ""                     # 结果摘要
    execution_time_ms: float = 0.0
    success: bool = True
    error: str = ""
    cached: bool = False
    risk_level: str = ""                         # 风险等级
    defense_trace_id: str = ""                   # 关联的安全防御追踪ID
    audit_log_id: str = ""                        # 审计日志ID

    def to_dict(self) -> dict:
        d = asdict(self)
        d["phase"] = self.phase.value
        # 截断过大的字段
        if len(d.get("result_summary", "")) > 2000:
            d["result_summary"] = d["result_summary"][:2000] + "...(truncated)"
        return d


@dataclass
class SafetyCheckRecord:
    """安全校验记录 — 三层防御的每次评估结果."""
    check_number: int
    timestamp: str
    target: str                                   # 被评估的目标（命令/工具名）
    target_type: str                              # terminal / tool / api_call
    layer_scores: Dict[str, Any]                 # 各层评分详情
    overall_verdict: str                          # ALLOW / CONFIRM / APPROVE / DENY
    overall_score: float
    decision_path: List[str]
    requires_confirmation: bool = False
    requires_approval: bool = False
    blocked: bool = False
    block_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class KnowledgeReference:
    """知识引用记录 — RAG 推理溯源."""
    ref_id: str                                   # 引用ID
    timestamp: str
    query: str                                     # 查询内容
    matched_docs: List[Dict[str, Any]]            # 匹配的文档片段
    relevance_scores: List[float]                 # 相关度分数
    used_in_step: int = 0                         # 在哪一步使用了
    applied: bool = False                         # 是否实际应用到推理中

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ErrorRecord:
    """错误/异常记录."""
    error_number: int
    timestamp: str
    phase: TraceStatus                            # 发生在哪个阶段
    error_type: str                                # 错误类型
    error_message: str
    stack_trace: str = ""
    recovered: bool = False                       # 是否已恢复
    recovery_action: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["phase"] = self.phase.value
        return d


@dataclass
class CheckpointData:
    """断点数据 — 用于断点续跑."""
    checkpoint_id: str
    timestamp: str
    status: TraceStatus
    completed_steps: int
    total_estimated_steps: int
    current_thought: Optional[Dict[str, Any]] = None
    pending_actions: List[Dict[str, Any]] = field(default_factory=list)
    partial_results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# =============================================================================
# 核心类: ReasoningTrace
# =============================================================================


class ReasoningTrace:
    """完整的推理链路追溯对象.

    一个 trace 对象代表一次完整的用户请求处理过程，
    从接收到最终结果的全链路记录。

    用法::

        trace = ReasoningTrace(
            user_message="帮我分析为什么 CPU 使用率很高",
            strategy="react",
        )
        with trace:
            # === 感知阶段 ===
            trace.update_status(TraceStatus.PERCEIVING)
            trace.record_thought(
                ThoughtType.OBSERVATION,
                content="检测到 CPU 使用率 95%，负载 8.2",
                confidence=0.98,
            )

            # === 推理阶段 ===
            trace.update_status(TraceStatus.REASONING)
            trace.record_thought(
                ThoughtType.HYPOTHESIS,
                content="可能原因: 1) 进程泄漏 2) 高负载任务",
                confidence=0.75,
            )

            # === 安全校验 ===
            trace.update_status(TraceStatus.SAFETY_CHECK)
            trace.record_safety_check(...)

            # === 执行阶段 ===
            trace.update_status(TraceStatus.EXECUTING)
            trace.record_action(...)

            # 完成
            trace.update_status(TraceStatus.COMPLETED)

        # 导出完整报告
        report = trace.to_full_report()
    """

    def __init__(
        self,
        user_message: str = "",
        *,
        trace_id: str = "",
        session_id: str = "",
        strategy: str = "react",
        user: str = "",
        max_turns: int = 15,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.trace_id = trace_id or f"trace-{uuid.uuid4().hex[:12]}"
        self.session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"
        self.user_message = user_message
        self.strategy = strategy
        self.user = user
        self.max_turns = max_turns
        self.metadata = metadata or {}

        # 时间线
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.finished_at: str = ""
        self.total_duration_ms: float = 0.0

        # 状态机
        self._status = TraceStatus.CREATED
        self.current_turn: int = 0

        # 记录列表
        self.thoughts: List[ThoughtRecord] = []
        self.actions: List[ActionRecord] = []
        self.observations: List[Dict[str, Any]] = []       # 原始观察数据
        self.safety_checks: List[SafetyCheckRecord] = []
        self.knowledge_refs: List[KnowledgeReference] = []
        self.errors: List[ErrorRecord] = []
        self.checkpoints: List[CheckpointData] = []

        # 统计
        self._thought_counter: int = 0
        self._action_counter: int = 0
        self._safety_counter: int = 0
        self._error_counter: int = 0
        self._checkpoint_counter: int = 0

        # 性能指标
        self.perception_duration_ms: float = 0.0
        self.reasoning_duration_ms: float = 0.0
        self.execution_duration_ms: float = 0.0
        self.total_tokens_used: int = 0
        self.llm_calls_count: int = 0

    @property
    def status(self) -> TraceStatus:
        return self._status

    # -----------------------------------------------------------------
    # 状态管理
    # -----------------------------------------------------------------

    def update_status(self, new_status: TraceStatus) -> None:
        """更新当前状态（只允许正向推进）."""
        status_order = [
            TraceStatus.CREATED,
            TraceStatus.PERCEIVING,
            TraceStatus.REASONING,
            TraceStatus.SAFETY_CHECK,
            TraceStatus.EXECUTING,
            TraceStatus.VERIFYING,
            TraceStatus.COMPLETED,
            TraceStatus.FAILED,
            TraceStatus.INTERRUPTED,
            TraceStatus.ROLLED_BACK,
        ]
        try:
            cur_idx = status_order.index(self._status)
            new_idx = status_order.index(new_status)
            if new_idx >= cur_idx:
                self._status = new_status
        except ValueError:
            pass  # 忽略无效状态转换

    # -----------------------------------------------------------------
    # 思考记录
    # -----------------------------------------------------------------

    def record_thought(
        self,
        thought_type: ThoughtType,
        content: str,
        *,
        confidence: float = 0.8,
        source_tool_ids: Optional[List[str]] = None,
        source_knowledge_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ThoughtRecord:
        """记录一条 Agent 思考.

        Args:
            thought_type: 思想类型
            content: 思考内容
            confidence: 置信度 (0-1)
            source_tool_ids: 关联的工具调用 ID 列表
            source_knowledge_ids: 引用的知识条目 ID 列表
            metadata: 附加元数据

        Returns:
            ThoughtRecord
        """
        self._thought_counter += 1
        record = ThoughtRecord(
            step_number=self._thought_counter,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            thought_type=thought_type,
            content=content,
            confidence=max(0.0, min(1.0, confidence)),
            source_tool_ids=source_tool_ids or [],
            source_knowledge_ids=source_knowledge_ids or [],
            metadata=metadata or {},
        )
        self.thoughts.append(record)
        logger.debug(f"[{self.trace_id}] Thought #{record.step_number} "
                      f"[{thought_type.value}] {content[:100]}")
        return record

    # -----------------------------------------------------------------
    # 操作记录
    # -----------------------------------------------------------------

    def record_action(
        self,
        tool_name: str,
        tool_id: str,
        arguments: Dict[str, Any],
        *,
        phase: ActionPhase = ActionPhase.EXECUTING,
        result_summary: str = "",
        execution_time_ms: float = 0.0,
        success: bool = True,
        error: str = "",
        cached: bool = False,
        risk_level: str = "",
        defense_trace_id: str = "",
        audit_log_id: str = "",
    ) -> ActionRecord:
        """记录一次工具/命令操作.

        Args:
            tool_name: 工具名称
            tool_id: 全局唯一工具ID
            arguments: 调用参数
            phase: 操作阶段
            result_summary: 结果摘要
            execution_time_ms: 执行耗时(ms)
            success: 是否成功
            error: 错误信息
            cached: 是否命中缓存
            risk_level: 风险等级
            defense_trace_id: 安全防御追踪ID
            audit_log_id: 审计日志ID

        Returns:
            ActionRecord
        """
        self._action_counter += 1
        record = ActionRecord(
            action_number=self._action_counter,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            phase=phase,
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=arguments,
            result_summary=result_summary,
            execution_time_ms=execution_time_ms,
            success=success,
            error=error,
            cached=cached,
            risk_level=risk_level,
            defense_trace_id=defense_trace_id,
            audit_log_id=audit_log_id,
        )
        self.actions.append(record)
        logger.debug(f"[{self.trace_id}] Action #{record.action_number} "
                      f"{tool_name} → {'OK' if success else 'FAIL'}")
        return record

    # -----------------------------------------------------------------
    # 安全校验记录
    # -----------------------------------------------------------------

    def record_safety_check(
        self,
        target: str,
        target_type: str,
        layer_scores: Dict[str, Any],
        overall_verdict: str,
        overall_score: float,
        decision_path: List[str],
        *,
        requires_confirmation: bool = False,
        requires_approval: bool = False,
        blocked: bool = False,
        block_reason: str = "",
    ) -> SafetyCheckRecord:
        """记录一次三层安全防御校验.

        Args:
            target: 被评估目标
            target_type: terminal/tool/api_call
            layer_scores: 各层评分详情
            overall_verdict: 综合判决
            overall_score: 综合评分
            decision_path: 决策路径
            requires_confirmation: 需要确认
            requires_approval: 需要审批
            blocked: 是否被拦截
            block_reason: 拦截原因

        Returns:
            SafetyCheckRecord
        """
        self._safety_counter += 1
        record = SafetyCheckRecord(
            check_number=self._safety_counter,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            target=target,
            target_type=target_type,
            layer_scores=layer_scores,
            overall_verdict=overall_verdict,
            overall_score=overall_score,
            decision_path=decision_path,
            requires_confirmation=requires_confirmation,
            requires_approval=requires_approval,
            blocked=blocked,
            block_reason=block_reason,
        )
        self.safety_checks.append(record)
        return record

    # -----------------------------------------------------------------
    # 知识引用（RAG 溯源）
    # -----------------------------------------------------------------

    def record_knowledge_ref(
        self,
        query: str,
        matched_docs: List[Dict[str, Any]],
        relevance_scores: List[float],
        *,
        used_in_step: int = 0,
        applied: bool = False,
    ) -> KnowledgeReference:
        """记录一次 RAG 知识检索与引用.

        用于实现「推理溯源」— 明确标注每一步推理参考了哪些文档。

        Returns:
            KnowledgeReference
        """
        ref = KnowledgeReference(
            ref_id=f"kr-{uuid.uuid4().hex[:8]}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            query=query,
            matched_docs=matched_docs,
            relevance_scores=relevance_scores,
            used_in_step=used_in_step,
            applied=applied,
        )
        self.knowledge_refs.append(ref)
        return ref

    # -----------------------------------------------------------------
    # 错误记录
    # -----------------------------------------------------------------

    def record_error(
        self,
        error_type: str,
        error_message: str,
        *,
        stack_trace: str = "",
        recovered: bool = False,
        recovery_action: str = "",
    ) -> ErrorRecord:
        """记录一个异常."""
        self._error_counter += 1
        record = ErrorRecord(
            error_number=self._error_counter,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            phase=self._status,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace[-3000:] if stack_trace else "",
            recovered=recovered,
            recovery_action=recovery_action,
        )
        self.errors.append(record)
        return record

    # -----------------------------------------------------------------
    # 断点续跑
    # -----------------------------------------------------------------

    def save_checkpoint(self, pending_actions=None) -> CheckpointData:
        """保存当前进度为断点（用于中断后恢复）.

        Args:
            pending_actions: 待执行的操作列表

        Returns:
            CheckpointData
        """
        self._checkpoint_counter += 1
        checkpoint = CheckpointData(
            checkpoint_id=f"cp-{uuid.uuid4().hex[:8]}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            status=self._status,
            completed_steps=self._thought_counter,
            total_estimated_steps=self.max_turns,
            current_thought=(
                self.thoughts[-1].to_dict() if self.thoughts else None
            ),
            pending_actions=pending_actions or [],
            partial_results={
                "observations_count": len(self.observations),
                "actions_count": len(self.actions),
                "last_action": (
                    self.actions[-1].to_dict() if self.actions else {}
                ),
            },
        )
        self.checkpoints.append(checkpoint)
        logger.info(f"[{self.trace_id}] Checkpoint saved: {checkpoint.checkpoint_id}")
        return checkpoint

    # -----------------------------------------------------------------
    # 上下文管理器
    # -----------------------------------------------------------------

    def __enter__(self) -> ReasoningTrace:
        _current_trace_var.set(self)
        self.update_status(TraceStatus.PERCEIVING)
        t_start = time.perf_counter()

        # 保存起始时间引用供 __exit__ 计算
        self.__start_perf = t_start
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        _current_trace_var.set(None)
        self.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")

        perf_start = getattr(self, "__start_perf", None)
        if perf_start is not None:
            self.total_duration_ms = (time.perf_counter() - perf_start) * 1000

        if exc_val:
            self.update_status(TraceStatus.FAILED)
            self.record_error(
                error_type=type(exc_val).__name__,
                error_message=str(exc_val),
                stack_trace="" if exc_tb is None else "".join([
                    line for line in exc_tb.format()
                ]),
            )
        elif self._status not in (TraceStatus.COMPLETED, TraceStatus.INTERRUPTED):
            self.update_status(TraceStatus.COMPLETED)

        # ★ 自动持久化到 JSONL（隐藏痛点修复）
        self._auto_persist()

    def _auto_persist(self) -> None:
        """退出上下文管理器时自动落盘（可被环境变量 TRACE_AUTO_PERSIST=0 禁用）."""
        import os as _os
        if _os.getenv("TRACE_AUTO_PERSIST", "1").lower() in ("0", "false", "no"):
            return
        try:
            self.persist_to_jsonl()
        except (OSError, IOError) as e:
            logger.warning(f"[{self.trace_id}] 自动持久化失败: {e}")

    def persist_to_jsonl(self, *, path: Optional[Path] = None) -> Path:
        """将全链路追踪记录写入 JSONL 文件.

        每次调用追加一行完整的 JSON 报告，实现:
          - 实时可查询（tail -f）
          - 支持 MapReduce / HBase 离线分析
          - 断点续跑恢复（from_jsonl 可重放）

        Args:
            path: 自定义输出路径（默认 data/traces/{yyyymmdd}.jsonl）

        Returns:
            实际写入的文件路径
        """
        out = Path(path) if path else _get_trace_dir() / f"{time.strftime('%Y%m%d')}.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as f:
            f.write(self.to_json(pretty=False) + "\n")
        logger.debug(f"[{self.trace_id}] 已持久化 → {out}")
        return out

    @classmethod
    def from_jsonl(cls, path: Path, *, trace_id: str = "") -> list[Dict[str, Any]]:
        """从 JSONL 文件中恢复追踪记录.

        Args:
            path: JSONL 文件路径
            trace_id: 可选，按 trace_id 过滤

        Returns:
            恢复的报告列表
        """
        records: list[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if not trace_id or record.get("trace_id") == trace_id:
                        records.append(record)
                except json.JSONDecodeError:
                    logger.warning(f"JSONL 解析错误，跳过行: {line[:100]}")
        return records

    # -----------------------------------------------------------------
    # 报告导出
    # -----------------------------------------------------------------

    def to_summary(self) -> Dict[str, Any]:
        """导出摘要报告（精简版，适合日志）."""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_message": self.user_message[:200],
            "strategy": self.strategy,
            "status": self._status.value,
            "duration_ms": round(self.total_duration_ms, 2),
            "turns_completed": self.current_turn,
            "total_thoughts": len(self.thoughts),
            "total_actions": len(self.actions),
            "success_rate": (
                round(sum(1 for a in self.actions if a.success) /
                      max(len(self.actions), 1), 2)
                if self.actions else 1.0
            ),
            "total_errors": len(self.errors),
            "safety_checks": len(self.safety_checks),
            "knowledge_refs": len(self.knowledge_refs),
            "checkpoints_saved": len(self.checkpoints),
            "llm_calls": self.llm_calls_count,
            "tokens_used": self.total_tokens_used,
        }

    def to_full_report(self) -> Dict[str, Any]:
        """导出完整报告（详细版，适合审计/复盘）."""
        report = self.to_summary()
        report.update({
            "user": self.user,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "max_turns": self.max_turns,
            "metadata": self.metadata,

            # 完整记录
            "thoughts": [t.to_dict() for t in self.thoughts],
            "actions": [a.to_dict() for a in self.actions],
            "observations": self.observations,
            "safety_checks": [sc.to_dict() for sc in self.safety_checks],
            "knowledge_refs": [kr.to_dict() for kr in self.knowledge_refs],
            "errors": [e.to_dict() for e in self.errors],
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],

            # 性能分解
            "performance_breakdown": {
                "perception_ms": round(self.perception_duration_ms, 2),
                "reasoning_ms": round(self.reasoning_duration_ms, 2),
                "execution_ms": round(self.execution_duration_ms, 2),
            },

            # 安全摘要
            "safety_summary": {
                "total_checks": len(self.safety_checks),
                "blocked_count": sum(1 for s in self.safety_checks if s.blocked),
                "approval_required": sum(1 for s in self.safety_checks if s.requires_approval),
                "confirmation_required": sum(1 for s in self.safety_checks if s.requires_confirmation),
                "avg_safety_score": (
                    round(sum(s.overall_score for s in self.safety_checks) /
                          max(len(self.safety_checks), 1), 2)
                    if self.safety_checks else 100.0
                ),
            },
        })
        return report

    def to_json(self, *, pretty: bool = True) -> str:
        """导出 JSON 格式."""
        indent = 2 if pretty else None
        return json.dumps(self.to_full_report(), indent=indent, ensure_ascii=False, default=str)

    def to_decision_tree(self) -> Dict[str, Any]:
        """导出推理决策树（结构化展示推理路径）.

        格式:
          {
            "root": {"thought": "...", "children": [...]}
          }
        """
        tree: Dict[str, Any] = {
            "trace_id": self.trace_id,
            "nodes": [],
            "edges": [],
        }

        for i, thought in enumerate(self.thoughts):
            node_id = f"T{i}"
            node = {
                "id": node_id,
                "type": "thought",
                "step": thought.step_number,
                "label": f"{thought.thought_type.value}",
                "content": thought.content[:300],
                "confidence": thought.confidence,
            }

            # 关联的操作
            linked_actions = [
                a for a in self.actions
                if any(f"action_{a.action_number}" in sid or
                       str(a.action_number) in (sid or "")
                       for sid in thought.source_tool_ids)
            ]
            if linked_actions:
                node["linked_actions"] = [
                    {"tool": a.tool_name, "ok": a.success}
                    for a in linked_actions
                ]

            # 关联的知识
            linked_kr = [
                kr for kr in self.knowledge_refs
                if kr.used_in_step == thought.step_number
            ]
            if linked_kr:
                node["linked_knowledge"] = [
                    {"query": kr.query[:80], "docs": len(kr.matched_docs)}
                    for kr in linked_kr
                ]

            tree["nodes"].append(node)

            # 边关系
            if i > 0:
                tree["edges"].append({"from": f"T{i-1}", "to": node_id})

        return tree


# =============================================================================
# 便捷函数
# =============================================================================

def get_current_trace() -> Optional[ReasoningTrace]:
    """获取当前上下文中的 ReasoningTrace 实例."""
    return _current_trace_var.get()


def get_current_trace_id() -> str:
    """获取当前 trace_id（兼容旧代码）."""
    trace = _current_trace_var.get()
    return trace.trace_id if trace else ""


def record_thought_global(thought_type: str, content: str, **kwargs) -> Optional[ThoughtRecord]:
    """全局便捷函数 — 向当前 trace 记录思考."""
    trace = _current_trace_var.get()
    if not trace:
        return None
    type_map = {
        "observation": ThoughtType.OBSERVATION,
        "hypothesis": ThoughtType.HYPOTHESIS,
        "reasoning": ThoughtType.REASONING,
        "planning": ThoughtType.PLANNING,
        "reflection": ThoughtType.REFLECTION,
        "decision": ThoughtType.DECISION,
        "uncertainty": ThoughtType.UNCERTAINTY,
    }
    tt = type_map.get(thought_type.lower(), ThoughtType.REASONING)
    return trace.record_thought(tt, content, **kwargs)

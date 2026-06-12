"""Pydantic 请求/响应模型"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


# ========== 认证 ==========
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    display_name: str = ""
    email: str = ""


class UserResponse(BaseModel):
    username: str
    role: str
    display_name: str
    email: str
    disabled: bool
    created_at: float
    last_login: Optional[float] = None


# ========== 感知层 ==========
class SystemMetricsResponse(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_avg: List[float]
    network_io: Dict[str, int]
    uptime_seconds: float
    process_count: int
    timestamp: float


class LogEntry(BaseModel):
    timestamp: str
    level: str
    source: str
    message: str


class LogQueryRequest(BaseModel):
    source: str = "syslog"
    level: Optional[str] = None
    keyword: Optional[str] = None
    limit: int = 100
    hours: int = 24


# ========== 安全层 ==========
class RiskAssessmentRequest(BaseModel):
    command: str
    context: Optional[str] = None


class RiskAssessmentResponse(BaseModel):
    level: str  # low / medium / high / critical
    score: float
    reasons: List[str]
    requires_approval: bool
    trace_id: Optional[str] = None
    verdict: Optional[str] = None


class DefenseEvaluateRequest(BaseModel):
    target: str
    target_type: str = "terminal"
    user_message: str = ""
    arguments: Dict[str, Any] = {}
    trace_id: Optional[str] = None
    sudo: bool = False


class ApprovalRequest(BaseModel):
    task_id: str = ""
    request_id: str = ""
    action: str  # approve / reject
    reason: str = ""


class ApprovalItem(BaseModel):
    task_id: str
    command: str
    risk_level: str
    requested_by: str
    requested_at: float
    status: str  # pending / approved / rejected


# ========== 执行器 ==========
class ExecuteRequest(BaseModel):
    command: str
    sandbox: bool = True
    timeout: int = 30
    confirm: bool = False
    approval_id: Optional[str] = None
    trace_id: Optional[str] = None


class ExecuteResponse(BaseModel):
    success: bool
    output: str
    error: str = ""
    duration_ms: float = 0
    risk_level: str = "READONLY"
    risk_label: str = ""
    execution_mode: str = "direct"
    rollback_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    auto_rollback_triggered: bool = False


class RollbackRequest(BaseModel):
    rollback_id: str


# ========== 快照管理 ==========
class SnapshotInfo(BaseModel):
    id: str
    created_at: str
    operation: str
    risk_level: str
    user: str = ""
    files_count: int = 0
    restored_at: Optional[str] = None
    restore_success: Optional[int] = None
    restore_failed: Optional[int] = None


class SnapshotRestoreResponse(BaseModel):
    success: bool
    snap_id: str
    operation: str = ""
    restored: List[str] = []
    failed: List[str] = []
    restored_count: int = 0
    failed_count: int = 0


# ========== Agent 对话 ==========
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tools_used: List[str] = []
    risk_level: str = "low"
    cost_tokens: int = 0
    token_usage: Dict[str, int] = {}
    cost_estimate: Dict[str, Any] = {}
    context_usage: Dict[str, Any] = {}
    execution_meta: Dict[str, Any] = {}
    plan_summary: Dict[str, Any] = {}
    model_used: str = ""
    skill_flow: str = ""
    trace_id: Optional[str] = None
    degradation_level: str = "S0"
    fallback_used: bool = False
    plan_id: Optional[str] = None
    mode: Optional[str] = None
    phase: Optional[str] = None
    agent: Optional[str] = None
    audit: Dict[str, Any] = {}


class PlanRequest(BaseModel):
    message: str
    batch_id: Optional[str] = None


class PlanStep(BaseModel):
    id: str
    layer: str
    title: str
    status: str = "pending"


class AnalysisPlanResponse(BaseModel):
    plan_id: str
    trace_id: str
    batch_id: Optional[str] = None
    intent: str
    message: str
    hint: str = ""
    tool_chain: List[str] = []
    skill_flow: Optional[str] = None
    steps: List[PlanStep] = []
    boundary_hits: List[Dict[str, Any]] = []
    knowledge_refs: List[Dict[str, Any]] = []
    static_snapshot: Dict[str, Any] = {}
    triple_perception: Dict[str, Any] = {}
    phase: Optional[str] = None
    phase_lock: Optional[str] = None
    requires_confirm: bool = False
    l2_verdict: Optional[str] = None
    status: str = "planned"


class ExecutePlanRequest(BaseModel):
    plan_id: str
    session_id: Optional[str] = None
    user_confirmed: bool = False


class L2PrecheckRequest(BaseModel):
    plan_id: str


class OrchestrateRequest(BaseModel):
    message: str
    batch_id: Optional[str] = None
    auto_execute: bool = False
    user_confirmed: bool = False


class AgentStageStatus(BaseModel):
    agent: str
    display_name: str
    layer: str
    status: str  # idle | running | done | blocked | error
    detail: str = ""


class OrchestrateResponse(BaseModel):
    plan: AnalysisPlanResponse
    l2: Dict[str, Any]
    agents: List[AgentStageStatus] = []
    execute: Optional[ChatResponse] = None
    audit: Optional[Dict[str, Any]] = None


# ========== 知识库 ==========
class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class KnowledgeResult(BaseModel):
    title: str
    content: str
    score: float
    source: str


# ========== MCP ==========
class McpServerInfo(BaseModel):
    name: str
    status: str  # running / stopped / error
    tools_count: int = 0
    protocol: str = "stdio"
    command: str = ""
    last_health_check: Optional[float] = None


class McpToolInfo(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any] = {}
    server_name: str = ""


# ========== 成本 ==========
class CostSummary(BaseModel):
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    model: str
    period_days: int


# ========== 告警 ==========
class AlertEvent(BaseModel):
    id: str
    level: str
    title: str
    message: str
    source: str
    timestamp: float
    read: bool = False


# ========== Trace ==========
class TraceNode(BaseModel):
    node_id: str
    name: str
    type: str
    timestamp: str
    duration_ms: float = 0
    status: str = "success"
    details: Dict[str, Any] = {}


class TraceLink(BaseModel):
    from_node: str
    to_node: str
    label: str = ""


class TraceVisualization(BaseModel):
    trace_id: str
    nodes: List[TraceNode]
    links: List[TraceLink]
    summary: Dict[str, Any]


# ========== 报告 ==========
class ReportRequest(BaseModel):
    report_type: str = "security"  # security / performance / audit
    hours: int = 24
    format: str = "json"  # json / pdf / png


# ========== 通用 ==========
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    uptime: float
    modules: Dict[str, str] = {}


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Any]
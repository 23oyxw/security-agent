"""模块接口定义 - 定义核心模块接口，减少直接依赖"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityResult:
    """安全检查结果"""
    allowed: bool
    risk_level: RiskLevel
    reason: str
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0


@dataclass
class TraceInfo:
    """追踪信息"""
    trace_id: str
    user_message: str
    stages: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ISecurityGate(ABC):
    """安全闸门接口"""
    
    @abstractmethod
    def check_command(self, command: str, user_message: str = "") -> SecurityResult:
        """检查命令安全性"""
        pass
    
    @abstractmethod
    def check_tool(self, tool_name: str, arguments: dict) -> SecurityResult:
        """检查工具安全性"""
        pass


class IStorage(ABC):
    """存储接口"""
    
    @abstractmethod
    def save_trace(self, trace_info: TraceInfo) -> bool:
        """保存追踪信息"""
        pass
    
    @abstractmethod
    def get_trace(self, trace_id: str) -> Optional[TraceInfo]:
        """获取追踪信息"""
        pass
    
    @abstractmethod
    def save_decision(self, decision: Dict[str, Any]) -> bool:
        """保存决策"""
        pass


class IExecutor(ABC):
    """执行器接口"""
    
    @abstractmethod
    def execute(self, command: str, timeout: int = 30) -> ExecutionResult:
        """执行命令"""
        pass
    
    @abstractmethod
    def execute_safe(self, command: str, user: str = "") -> ExecutionResult:
        """安全执行命令"""
        pass


class IMonitor(ABC):
    """监控接口"""
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        pass
    
    @abstractmethod
    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取告警"""
        pass
    
    @abstractmethod
    def record_metric(self, name: str, value: float) -> bool:
        """记录指标"""
        pass


class IVisualizer(ABC):
    """可视化接口"""
    
    @abstractmethod
    def visualize_trace(self, trace_id: str) -> Dict[str, Any]:
        """可视化追踪"""
        pass
    
    @abstractmethod
    def generate_report(self, trace_id: str) -> str:
        """生成报告"""
        pass


class IPluginManager(ABC):
    """插件管理器接口"""
    
    @abstractmethod
    def register_plugin(self, plugin_info: Dict[str, Any]) -> bool:
        """注册插件"""
        pass
    
    @abstractmethod
    def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """获取插件"""
        pass
    
    @abstractmethod
    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出插件"""
        pass


class IConfirmationManager(ABC):
    """确认管理器接口"""
    
    @abstractmethod
    def create_request(self, request_data: Dict[str, Any]) -> str:
        """创建确认请求"""
        pass
    
    @abstractmethod
    def approve_request(self, request_id: str, reason: str = "") -> bool:
        """批准请求"""
        pass
    
    @abstractmethod
    def reject_request(self, request_id: str, reason: str = "") -> bool:
        """拒绝请求"""
        pass
    
    @abstractmethod
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """获取待处理请求"""
        pass

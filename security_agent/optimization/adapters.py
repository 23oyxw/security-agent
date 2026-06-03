"""适配器工厂 - 将现有模块适配到抽象接口"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from security_agent.interfaces import (
    ISecurityGate, IStorage, IExecutor, IMonitor, 
    IVisualizer, IPluginManager, IConfirmationManager,
    RiskLevel, SecurityResult, ExecutionResult, TraceInfo
)


class SecurityGateAdapter(ISecurityGate):
    """安全闸门适配器 - 适配SafetyGate到ISecurityGate接口"""
    
    def __init__(self, gate_instance=None):
        self._gate = gate_instance
    
    def check_command(self, command: str, user_message: str = "") -> SecurityResult:
        """检查命令安全性"""
        if self._gate is None:
            # 延迟导入避免循环依赖
            from security_agent.safety_gate import SafetyGate
            self._gate = SafetyGate()
        
        try:
            result = self._gate.evaluate_terminal(
                command=command,
                user_message=user_message
            )
            
            # 映射风险等级
            risk_mapping = {
                "LOW": RiskLevel.LOW,
                "MEDIUM": RiskLevel.MEDIUM,
                "HIGH": RiskLevel.HIGH,
                "CRITICAL": RiskLevel.CRITICAL
            }
            
            risk_level = RiskLevel.LOW
            if hasattr(result, 'risk') and result.risk:
                risk_level = risk_mapping.get(
                    result.risk.level.name if hasattr(result.risk.level, 'name') else str(result.risk.level),
                    RiskLevel.LOW
                )
            
            allowed = result.verdict.value in ["allow", "confirm", "backup_confirm"]
            
            return SecurityResult(
                allowed=allowed,
                risk_level=risk_level,
                reason=result.message if hasattr(result, 'message') else "",
                details=result.to_dict() if hasattr(result, 'to_dict') else {}
            )
        except Exception as e:
            return SecurityResult(
                allowed=False,
                risk_level=RiskLevel.HIGH,
                reason=f"安全检查失败: {str(e)}"
            )
    
    def check_tool(self, tool_name: str, arguments: dict) -> SecurityResult:
        """检查工具安全性"""
        if self._gate is None:
            from security_agent.safety_gate import SafetyGate
            self._gate = SafetyGate()
        
        try:
            result = self._gate.evaluate_tool(
                tool_name=tool_name,
                arguments=arguments
            )
            
            allowed = result.verdict.value in ["allow", "confirm", "backup_confirm"]
            
            return SecurityResult(
                allowed=allowed,
                risk_level=RiskLevel.MEDIUM,
                reason=result.message if hasattr(result, 'message') else "",
                details=result.to_dict() if hasattr(result, 'to_dict') else {}
            )
        except Exception as e:
            return SecurityResult(
                allowed=False,
                risk_level=RiskLevel.HIGH,
                reason=f"工具检查失败: {str(e)}"
            )


class StorageAdapter(IStorage):
    """存储适配器 - 适配多个存储模块到IStorage接口"""
    
    def __init__(self):
        self._trace_storage = None
        self._gate_storage = None
    
    def _get_trace_storage(self):
        if self._trace_storage is None:
            from security_agent.storage import get_trace_storage
            self._trace_storage = get_trace_storage()
        return self._trace_storage
    
    def _get_gate_storage(self):
        if self._gate_storage is None:
            from security_agent.storage import get_gate_storage
            self._gate_storage = get_gate_storage()
        return self._gate_storage
    
    def save_trace(self, trace_info: TraceInfo) -> bool:
        """保存追踪信息"""
        try:
            storage = self._get_trace_storage()
            # 这里需要根据实际的TraceStorage接口进行适配
            return True
        except Exception as e:
            print(f"保存追踪失败: {e}")
            return False
    
    def get_trace(self, trace_id: str) -> Optional[TraceInfo]:
        """获取追踪信息"""
        try:
            storage = self._get_trace_storage()
            # 这里需要根据实际的TraceStorage接口进行适配
            return None
        except Exception as e:
            print(f"获取追踪失败: {e}")
            return None
    
    def save_decision(self, decision: dict) -> bool:
        """保存决策"""
        try:
            storage = self._get_gate_storage()
            storage.save_decision(
                decision_id=decision.get("decision_id", ""),
                trace_id=decision.get("trace_id"),
                user_message=decision.get("user_message"),
                command=decision.get("command"),
                tool_name=decision.get("tool_name"),
                risk_level=decision.get("risk_level"),
                verdict=decision.get("verdict"),
                allowed=decision.get("allowed", True),
                reason=decision.get("reason"),
                metadata=decision.get("metadata")
            )
            return True
        except Exception as e:
            print(f"保存决策失败: {e}")
            return False


class MonitorAdapter(IMonitor):
    """监控适配器 - 适配RiskMonitor到IMonitor接口"""
    
    def __init__(self):
        self._monitor = None
    
    def _get_monitor(self):
        if self._monitor is None:
            from security_agent.monitor import get_risk_monitor
            self._monitor = get_risk_monitor()
        return self._monitor
    
    def get_status(self) -> dict:
        """获取状态"""
        try:
            monitor = self._get_monitor()
            return monitor.get_risk_summary()
        except Exception as e:
            print(f"获取状态失败: {e}")
            return {"error": str(e)}
    
    def get_alerts(self, limit: int = 50) -> list:
        """获取告警"""
        try:
            monitor = self._get_monitor()
            alerts = monitor.get_alerts(limit=limit)
            return [alert.to_dict() for alert in alerts]
        except Exception as e:
            print(f"获取告警失败: {e}")
            return []
    
    def record_metric(self, name: str, value: float) -> bool:
        """记录指标"""
        try:
            monitor = self._get_monitor()
            monitor.update_metric(name, value)
            return True
        except Exception as e:
            print(f"记录指标失败: {e}")
            return False


class ConfirmationAdapter(IConfirmationManager):
    """确认管理器适配器"""
    
    def __init__(self):
        self._manager = None
    
    def _get_manager(self):
        if self._manager is None:
            from security_agent.confirm import get_confirmation_manager
            self._manager = get_confirmation_manager()
        return self._manager
    
    def create_request(self, request_data: dict) -> str:
        """创建确认请求"""
        try:
            from security_agent.confirm import ConfirmationLevel
            manager = self._get_manager()
            
            # 映射确认级别
            level_mapping = {
                "confirm": ConfirmationLevel.CONFIRM,
                "approve": ConfirmationLevel.APPROVE,
                "escalate": ConfirmationLevel.ESCALATE
            }
            
            level = level_mapping.get(
                request_data.get("confirmation_level", "confirm"),
                ConfirmationLevel.CONFIRM
            )
            
            request = manager.create_request(
                trace_id=request_data.get("trace_id", ""),
                user_message=request_data.get("user_message", ""),
                action_description=request_data.get("action_description", ""),
                risk_level=request_data.get("risk_level", "LOW"),
                confirmation_level=level,
                metadata=request_data.get("metadata")
            )
            return request.request_id
        except Exception as e:
            print(f"创建确认请求失败: {e}")
            return ""
    
    def approve_request(self, request_id: str, reason: str = "") -> bool:
        """批准请求"""
        try:
            manager = self._get_manager()
            return manager.approve_request(request_id, "user", reason)
        except Exception as e:
            print(f"批准请求失败: {e}")
            return False
    
    def reject_request(self, request_id: str, reason: str = "") -> bool:
        """拒绝请求"""
        try:
            manager = self._get_manager()
            return manager.reject_request(request_id, "user", reason)
        except Exception as e:
            print(f"拒绝请求失败: {e}")
            return False
    
    def get_pending_requests(self) -> list:
        """获取待处理请求"""
        try:
            manager = self._get_manager()
            requests = manager.list_pending_requests()
            return [req.to_dict() for req in requests]
        except Exception as e:
            print(f"获取待处理请求失败: {e}")
            return []


class AdapterFactory:
    """适配器工厂 - 创建和管理适配器实例"""
    
    _instances = {}
    
    @classmethod
    def get_security_gate(cls) -> SecurityGateAdapter:
        """获取安全闸门适配器"""
        if "security_gate" not in cls._instances:
            cls._instances["security_gate"] = SecurityGateAdapter()
        return cls._instances["security_gate"]
    
    @classmethod
    def get_storage(cls) -> StorageAdapter:
        """获取存储适配器"""
        if "storage" not in cls._instances:
            cls._instances["storage"] = StorageAdapter()
        return cls._instances["storage"]
    
    @classmethod
    def get_monitor(cls) -> MonitorAdapter:
        """获取监控适配器"""
        if "monitor" not in cls._instances:
            cls._instances["monitor"] = MonitorAdapter()
        return cls._instances["monitor"]
    
    @classmethod
    def get_confirmation(cls) -> ConfirmationAdapter:
        """获取确认管理器适配器"""
        if "confirmation" not in cls._instances:
            cls._instances["confirmation"] = ConfirmationAdapter()
        return cls._instances["confirmation"]
    
    @classmethod
    def reset(cls):
        """重置所有适配器实例"""
        cls._instances.clear()

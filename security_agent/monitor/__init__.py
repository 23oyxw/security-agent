"""监控模块"""

from security_agent.monitor.risk_monitor import (
    RiskMonitor,
    RiskMetric,
    SystemAlert,
    RiskStatus,
    AlertLevel,
    get_risk_monitor
)

from security_agent.monitor.service import (
    MonitorService,
    get_monitor_service
)

def get_monitor_service_instance():
    """获取全局监控服务实例（与 get_monitor_service 相同）"""
    return get_monitor_service()

__all__ = [
    "RiskMonitor",
    "RiskMetric", 
    "SystemAlert",
    "RiskStatus",
    "AlertLevel",
    "get_risk_monitor",
    "MonitorService",
    "get_monitor_service",
    "get_monitor_service_instance"
]

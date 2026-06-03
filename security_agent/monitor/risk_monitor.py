"""实时风险监控模块 - 动态监控系统风险状态"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RiskStatus(str, Enum):
    """风险状态"""
    NORMAL = "normal"          # 正常
    WARNING = "warning"        # 警告
    DANGER = "danger"          # 危险
    CRITICAL = "critical"      # 严重


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class RiskMetric:
    """风险指标"""
    name: str
    value: float
    threshold_warning: float
    threshold_critical: float
    description: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def status(self) -> RiskStatus:
        """计算当前状态"""
        if self.value >= self.threshold_critical:
            return RiskStatus.CRITICAL
        elif self.value >= self.threshold_warning:
            return RiskStatus.WARNING
        else:
            return RiskStatus.NORMAL


@dataclass
class SystemAlert:
    """系统告警"""
    alert_id: str
    level: AlertLevel
    message: str
    source: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "message": self.message,
            "source": self.source,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "created_at": self.created_at,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by
        }


class RiskMonitor:
    """实时风险监控器"""
    
    def __init__(self, db_path: str = "data/risk_monitor.db"):
        """
        初始化风险监控器
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # 风险指标
        self.metrics: Dict[str, RiskMetric] = {}
        self._init_default_metrics()
        
        # 告警列表
        self.alerts: List[SystemAlert] = []
        
        # 监控线程
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 回调函数
        self._alert_callbacks = []
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            # 风险指标表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    value REAL,
                    threshold_warning REAL,
                    threshold_critical REAL,
                    description TEXT,
                    status TEXT,
                    updated_at TIMESTAMP
                )
            """)
            
            # 告警记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE NOT NULL,
                    level TEXT,
                    message TEXT,
                    source TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    threshold REAL,
                    created_at TIMESTAMP,
                    acknowledged BOOLEAN DEFAULT 0,
                    acknowledged_at TIMESTAMP,
                    acknowledged_by TEXT
                )
            """)
            
            # 风险历史表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP,
                    metrics TEXT,
                    overall_status TEXT,
                    alert_count INTEGER
                )
            """)
            
            # 索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_name 
                ON risk_metrics(name)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_created_at 
                ON system_alerts(created_at)
            """)
            
            conn.commit()
    
    def _init_default_metrics(self):
        """初始化默认风险指标"""
        default_metrics = [
            RiskMetric(
                name="cpu_usage",
                value=0.0,
                threshold_warning=70.0,
                threshold_critical=90.0,
                description="CPU使用率"
            ),
            RiskMetric(
                name="memory_usage",
                value=0.0,
                threshold_warning=75.0,
                threshold_critical=90.0,
                description="内存使用率"
            ),
            RiskMetric(
                name="disk_usage",
                value=0.0,
                threshold_warning=80.0,
                threshold_critical=95.0,
                description="磁盘使用率"
            ),
            RiskMetric(
                name="error_rate",
                value=0.0,
                threshold_warning=5.0,
                threshold_critical=10.0,
                description="错误率(%)"
            ),
            RiskMetric(
                name="response_time",
                value=0.0,
                threshold_warning=1000.0,
                threshold_critical=5000.0,
                description="响应时间(ms)"
            ),
            RiskMetric(
                name="security_incidents",
                value=0.0,
                threshold_warning=1.0,
                threshold_critical=3.0,
                description="安全事件数"
            )
        ]
        
        for metric in default_metrics:
            self.metrics[metric.name] = metric
            self._save_metric(metric)
    
    def _save_metric(self, metric: RiskMetric):
        """保存指标到数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO risk_metrics 
                   (name, value, threshold_warning, threshold_critical, description, status, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (metric.name, metric.value, metric.threshold_warning,
                 metric.threshold_critical, metric.description,
                 metric.status.value, metric.updated_at)
            )
            conn.commit()
    
    def update_metric(self, name: str, value: float) -> Optional[RiskMetric]:
        """更新指标值"""
        if name not in self.metrics:
            return None
        
        metric = self.metrics[name]
        old_status = metric.status
        metric.value = value
        metric.updated_at = datetime.now().isoformat()
        
        # 保存到数据库
        self._save_metric(metric)
        
        # 检查是否需要告警
        if metric.status != old_status:
            self._check_metric_alert(metric, old_status)
        
        return metric
    
    def _check_metric_alert(self, metric: RiskMetric, old_status: RiskStatus):
        """检查指标告警"""
        if metric.status == RiskStatus.CRITICAL:
            alert = SystemAlert(
                alert_id=f"alert_{int(time.time())}_{metric.name}",
                level=AlertLevel.CRITICAL,
                message=f"{metric.description}严重告警: 当前值{metric.value}，阈值{metric.threshold_critical}",
                source="risk_monitor",
                metric_name=metric.name,
                metric_value=metric.value,
                threshold=metric.threshold_critical
            )
            self._add_alert(alert)
        
        elif metric.status == RiskStatus.WARNING and old_status == RiskStatus.NORMAL:
            alert = SystemAlert(
                alert_id=f"alert_{int(time.time())}_{metric.name}",
                level=AlertLevel.WARNING,
                message=f"{metric.description}警告: 当前值{metric.value}，阈值{metric.threshold_warning}",
                source="risk_monitor",
                metric_name=metric.name,
                metric_value=metric.value,
                threshold=metric.threshold_warning
            )
            self._add_alert(alert)
    
    def _add_alert(self, alert: SystemAlert):
        """添加告警"""
        self.alerts.append(alert)
        
        # 保存到数据库
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO system_alerts 
                   (alert_id, level, message, source, metric_name, metric_value, threshold, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (alert.alert_id, alert.level.value, alert.message, alert.source,
                 alert.metric_name, alert.metric_value, alert.threshold, alert.created_at)
            )
            conn.commit()
        
        # 触发回调
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"告警回调执行失败: {e}")
    
    def add_alert_callback(self, callback):
        """添加告警回调"""
        self._alert_callbacks.append(callback)
    
    def get_metric(self, name: str) -> Optional[RiskMetric]:
        """获取指标"""
        return self.metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, RiskMetric]:
        """获取所有指标"""
        return self.metrics.copy()
    
    def get_overall_status(self) -> RiskStatus:
        """获取总体风险状态"""
        statuses = [metric.status for metric in self.metrics.values()]
        
        if RiskStatus.CRITICAL in statuses:
            return RiskStatus.CRITICAL
        elif RiskStatus.DANGER in statuses:
            return RiskStatus.DANGER
        elif RiskStatus.WARNING in statuses:
            return RiskStatus.WARNING
        else:
            return RiskStatus.NORMAL
    
    def get_alerts(self, limit: int = 50, unacknowledged_only: bool = False) -> List[SystemAlert]:
        """获取告警列表"""
        alerts = self.alerts
        
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        
        return sorted(alerts, key=lambda x: x.created_at, reverse=True)[:limit]
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """确认告警"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now().isoformat()
                alert.acknowledged_by = acknowledged_by
                
                # 更新数据库
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """UPDATE system_alerts 
                           SET acknowledged = 1, acknowledged_at = ?, acknowledged_by = ?
                           WHERE alert_id = ?""",
                        (alert.acknowledged_at, acknowledged_by, alert_id)
                    )
                    conn.commit()
                
                return True
        
        return False
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """获取风险摘要"""
        metrics_summary = {}
        for name, metric in self.metrics.items():
            metrics_summary[name] = {
                "value": metric.value,
                "status": metric.status.value,
                "threshold_warning": metric.threshold_warning,
                "threshold_critical": metric.threshold_critical
            }
        
        alerts_summary = {
            "total": len(self.alerts),
            "unacknowledged": len([a for a in self.alerts if not a.acknowledged]),
            "critical": len([a for a in self.alerts if a.level == AlertLevel.CRITICAL]),
            "warning": len([a for a in self.alerts if a.level == AlertLevel.WARNING])
        }
        
        return {
            "overall_status": self.get_overall_status().value,
            "metrics": metrics_summary,
            "alerts": alerts_summary,
            "updated_at": datetime.now().isoformat()
        }
    
    def save_snapshot(self):
        """保存风险快照"""
        summary = self.get_risk_summary()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO risk_history 
                   (timestamp, metrics, overall_status, alert_count) 
                   VALUES (?, ?, ?, ?)""",
                (datetime.now().isoformat(), json.dumps(summary["metrics"]),
                 summary["overall_status"], summary["alerts"]["total"])
            )
            conn.commit()
    
    def start_monitoring(self, interval: int = 30):
        """开始监控"""
        if self._monitoring:
            return
        
        self._monitoring = True
        
        def monitor_loop():
            while self._monitoring:
                try:
                    # 保存快照
                    self.save_snapshot()
                    
                    # 等待下一次检查
                    time.sleep(interval)
                except Exception as e:
                    print(f"监控循环错误: {e}")
                    time.sleep(interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)


# 全局单例
_risk_monitor_instance: Optional[RiskMonitor] = None


def get_risk_monitor() -> RiskMonitor:
    """获取全局风险监控器实例"""
    global _risk_monitor_instance
    if _risk_monitor_instance is None:
        _risk_monitor_instance = RiskMonitor()
    return _risk_monitor_instance

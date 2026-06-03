"""系统健康检查 - 监控系统各模块健康状态"""

from __future__ import annotations

import time
import os
import sqlite3
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path


class HealthStatus(str, Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    check_time: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "check_time": datetime.fromtimestamp(self.check_time).isoformat(),
            "duration_ms": round(self.duration_ms, 2)
        }


@dataclass
class HealthCheckConfig:
    """健康检查配置"""
    name: str
    check_func: Callable
    interval: int = 60  # 检查间隔（秒）
    timeout: int = 10  # 超时时间（秒）
    enabled: bool = True
    critical: bool = False  # 是否为关键检查


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self._checks: Dict[str, HealthCheckConfig] = {}
        self._results: Dict[str, HealthCheckResult] = {}
        self._history: Dict[str, List[HealthCheckResult]] = {}
        self._last_check_time: Dict[str, float] = {}
        self._register_default_checks()
    
    def _register_default_checks(self):
        """注册默认检查"""
        self.register_check(
            name="database",
            check_func=self._check_database,
            interval=30,
            critical=True
        )
        
        self.register_check(
            name="disk_space",
            check_func=self._check_disk_space,
            interval=60
        )
        
        self.register_check(
            name="memory_usage",
            check_func=self._check_memory_usage,
            interval=60
        )
    
    def register_check(
        self,
        name: str,
        check_func: Callable,
        interval: int = 60,
        timeout: int = 10,
        enabled: bool = True,
        critical: bool = False
    ):
        """注册健康检查"""
        self._checks[name] = HealthCheckConfig(
            name=name,
            check_func=check_func,
            interval=interval,
            timeout=timeout,
            enabled=enabled,
            critical=critical
        )
    
    def run_check(self, name: str) -> HealthCheckResult:
        """运行单个检查"""
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="检查未注册"
            )
        
        config = self._checks[name]
        if not config.enabled:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="检查已禁用"
            )
        
        start_time = time.time()
        try:
            result = config.check_func()
            duration = (time.time() - start_time) * 1000
            result.duration_ms = duration
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"检查异常: {str(e)}",
                duration_ms=duration
            )
        
        # 保存结果
        self._results[name] = result
        self._last_check_time[name] = time.time()
        
        # 添加到历史
        if name not in self._history:
            self._history[name] = []
        self._history[name].append(result)
        
        # 保留最近100条记录
        if len(self._history[name]) > 100:
            self._history[name] = self._history[name][-100:]
        
        return result
    
    def run_all_checks(self, force: bool = False) -> Dict[str, HealthCheckResult]:
        """运行所有检查"""
        results = {}
        
        for name, config in self._checks.items():
            if not config.enabled:
                continue
            
            # 检查是否需要运行
            if not force:
                last_check = self._last_check_time.get(name, 0)
                if time.time() - last_check < config.interval:
                    # 使用缓存结果
                    if name in self._results:
                        results[name] = self._results[name]
                        continue
            
            results[name] = self.run_check(name)
        
        return results
    
    def get_status(self) -> HealthStatus:
        """获取整体状态"""
        if not self._results:
            return HealthStatus.UNKNOWN
        
        critical_unhealthy = False
        any_degraded = False
        
        for name, result in self._results.items():
            config = self._checks.get(name)
            
            if result.status == HealthStatus.UNHEALTHY:
                if config and config.critical:
                    critical_unhealthy = True
            elif result.status == HealthStatus.DEGRADED:
                any_degraded = True
        
        if critical_unhealthy:
            return HealthStatus.UNHEALTHY
        elif any_degraded:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def get_results(self) -> Dict[str, Dict[str, Any]]:
        """获取所有结果"""
        return {name: result.to_dict() for name, result in self._results.items()}
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        results = self.get_results()
        overall_status = self.get_status()
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "checks": results,
            "summary": {
                "total_checks": len(self._checks),
                "healthy": sum(1 for r in self._results.values() if r.status == HealthStatus.HEALTHY),
                "degraded": sum(1 for r in self._results.values() if r.status == HealthStatus.DEGRADED),
                "unhealthy": sum(1 for r in self._results.values() if r.status == HealthStatus.UNHEALTHY),
                "unknown": sum(1 for r in self._results.values() if r.status == HealthStatus.UNKNOWN)
            }
        }
    
    def get_history(self, name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取检查历史"""
        if name not in self._history:
            return []
        
        history = self._history[name][-limit:]
        return [result.to_dict() for result in history]
    
    # 默认检查函数
    def _check_database(self) -> HealthCheckResult:
        """检查数据库"""
        try:
            # 检查数据库文件是否存在
            db_path = "data/main.db"
            if not os.path.exists(db_path):
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.DEGRADED,
                    message="数据库文件不存在",
                    details={"path": db_path}
                )
            
            # 尝试连接数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            
            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="数据库连接正常",
                details={"path": db_path, "size": os.path.getsize(db_path)}
            )
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"数据库连接失败: {str(e)}"
            )
    
    def _check_disk_space(self) -> HealthCheckResult:
        """检查磁盘空间"""
        try:
            stat = os.statvfs(".")
            total = stat.f_frsize * stat.f_blocks
            free = stat.f_frsize * stat.f_bavail
            used = total - free
            usage_percent = (used / total * 100) if total > 0 else 0
            
            if usage_percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"磁盘空间严重不足: {usage_percent:.1f}%"
            elif usage_percent > 80:
                status = HealthStatus.DEGRADED
                message = f"磁盘空间不足: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"磁盘空间正常: {usage_percent:.1f}%"
            
            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "total_gb": round(total / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "usage_percent": round(usage_percent, 2)
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"磁盘检查失败: {str(e)}"
            )
    
    def _check_memory_usage(self) -> HealthCheckResult:
        """检查内存使用"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            if usage_percent > 90:
                status = HealthStatus.UNHEALTHY
                message = f"内存使用过高: {usage_percent}%"
            elif usage_percent > 80:
                status = HealthStatus.DEGRADED
                message = f"内存使用较高: {usage_percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"内存使用正常: {usage_percent}%"
            
            return HealthCheckResult(
                name="memory_usage",
                status=status,
                message=message,
                details={
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "usage_percent": usage_percent
                }
            )
        except ImportError:
            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.UNKNOWN,
                message="psutil未安装，跳过内存检查"
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory_usage",
                status=HealthStatus.UNKNOWN,
                message=f"内存检查失败: {str(e)}"
            )


# 全局健康检查器
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def check_health(force: bool = False) -> Dict[str, Any]:
    """检查健康状态"""
    return get_health_checker().run_all_checks(force=force)


def get_health_status() -> Dict[str, Any]:
    """获取健康状态"""
    return get_health_checker().get_summary()

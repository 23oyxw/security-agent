"""统一优化管理器 - 管理和监控所有优化功能"""

from __future__ import annotations

import time
import threading
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from contextlib import contextmanager
from collections import defaultdict


class OptimizationStatus(str, Enum):
    """优化状态"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    DEGRADED = "degraded"


@dataclass
class OptimizationMetrics:
    """优化指标"""
    cache_hits: int = 0
    cache_misses: int = 0
    async_operations: int = 0
    db_queries: int = 0
    errors_caught: int = 0
    config_reloads: int = 0
    di_resolves: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hit_rate, 2),
            "async_operations": self.async_operations,
            "db_queries": self.db_queries,
            "errors_caught": self.errors_caught,
            "config_reloads": self.config_reloads,
            "di_resolves": self.di_resolves
        }


@dataclass
class OptimizationModule:
    """优化模块信息"""
    name: str
    status: OptimizationStatus
    enabled: bool = True
    initialized: bool = False
    error_count: int = 0
    last_error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class OptimizationManager:
    """优化管理器"""
    
    _instance: Optional[OptimizationManager] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._modules: Dict[str, OptimizationModule] = {}
            self._metrics = OptimizationMetrics()
            self._start_time = time.time()
            self._hooks: Dict[str, List[Callable]] = defaultdict(list)
            self._initialized_modules = set()
    
    def register_module(self, name: str, enabled: bool = True) -> OptimizationModule:
        """注册优化模块"""
        module = OptimizationModule(
            name=name,
            status=OptimizationStatus.ENABLED if enabled else OptimizationStatus.DISABLED,
            enabled=enabled
        )
        self._modules[name] = module
        return module
    
    def get_module(self, name: str) -> Optional[OptimizationModule]:
        """获取优化模块"""
        return self._modules.get(name)
    
    def enable_module(self, name: str) -> bool:
        """启用优化模块"""
        if name in self._modules:
            self._modules[name].enabled = True
            self._modules[name].status = OptimizationStatus.ENABLED
            return True
        return False
    
    def disable_module(self, name: str) -> bool:
        """禁用优化模块"""
        if name in self._modules:
            self._modules[name].enabled = False
            self._modules[name].status = OptimizationStatus.DISABLED
            return True
        return False
    
    def record_metric(self, metric_name: str, value: int = 1):
        """记录指标"""
        if hasattr(self._metrics, metric_name):
            current = getattr(self._metrics, metric_name)
            setattr(self._metrics, metric_name, current + value)
    
    def increment_cache_hit(self):
        """增加缓存命中"""
        self.record_metric("cache_hits")
    
    def increment_cache_miss(self):
        """增加缓存未命中"""
        self.record_metric("cache_misses")
    
    def increment_async_operation(self):
        """增加异步操作"""
        self.record_metric("async_operations")
    
    def increment_db_query(self):
        """增加数据库查询"""
        self.record_metric("db_queries")
    
    def increment_error_caught(self):
        """增加错误捕获"""
        self.record_metric("errors_caught")
    
    def increment_config_reload(self):
        """增加配置重载"""
        self.record_metric("config_reloads")
    
    def increment_di_resolve(self):
        """增加DI解析"""
        self.record_metric("di_resolves")
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return self._metrics.to_dict()
    
    def get_uptime(self) -> float:
        """获取运行时间（秒）"""
        return time.time() - self._start_time
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        modules_status = {}
        for name, module in self._modules.items():
            modules_status[name] = {
                "status": module.status.value,
                "enabled": module.enabled,
                "initialized": module.initialized,
                "error_count": module.error_count
            }
        
        return {
            "uptime_seconds": round(self.get_uptime(), 2),
            "modules": modules_status,
            "metrics": self.get_metrics(),
            "total_modules": len(self._modules),
            "enabled_modules": sum(1 for m in self._modules.values() if m.enabled)
        }
    
    @contextmanager
    def track_operation(self, operation_name: str):
        """追踪操作"""
        start_time = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start_time
            # 可以在这里记录操作时间
            pass
    
    def add_hook(self, event: str, callback: Callable):
        """添加钩子"""
        self._hooks[event].append(callback)
    
    def trigger_hook(self, event: str, *args, **kwargs):
        """触发钩子"""
        for callback in self._hooks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"钩子执行失败 {event}: {e}")
    
    def generate_report(self) -> Dict[str, Any]:
        """生成优化报告"""
        metrics = self.get_metrics()
        status = self.get_status()
        
        # 计算优化效果
        cache_efficiency = metrics.get("cache_hit_rate", 0)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_hours": round(self.get_uptime() / 3600, 2),
            "modules": status["modules"],
            "metrics": metrics,
            "summary": {
                "total_operations": sum([
                    metrics.get("async_operations", 0),
                    metrics.get("db_queries", 0)
                ]),
                "cache_efficiency": cache_efficiency,
                "error_rate": round(
                    metrics.get("errors_caught", 0) / max(1, metrics.get("db_queries", 1)) * 100,
                    2
                ),
                "optimization_score": self._calculate_optimization_score(metrics)
            }
        }
    
    def _calculate_optimization_score(self, metrics: Dict[str, Any]) -> int:
        """计算优化得分"""
        score = 100
        
        # 缓存效率
        cache_rate = metrics.get("cache_hit_rate", 0)
        if cache_rate < 50:
            score -= 20
        elif cache_rate < 70:
            score -= 10
        
        # 错误率
        total_ops = metrics.get("db_queries", 1)
        error_rate = metrics.get("errors_caught", 0) / total_ops if total_ops > 0 else 0
        if error_rate > 0.1:
            score -= 20
        elif error_rate > 0.05:
            score -= 10
        
        return max(0, score)
    
    @classmethod
    def reset(cls):
        """重置管理器"""
        with cls._lock:
            cls._instance = None


# 全局优化管理器
_optimization_manager: Optional[OptimizationManager] = None


def get_optimization_manager() -> OptimizationManager:
    """获取全局优化管理器"""
    global _optimization_manager
    if _optimization_manager is None:
        _optimization_manager = OptimizationManager()
    return _optimization_manager


def track_cache_hit():
    """追踪缓存命中"""
    get_optimization_manager().increment_cache_hit()


def track_cache_miss():
    """追踪缓存未命中"""
    get_optimization_manager().increment_cache_miss()


def track_async_operation():
    """追踪异步操作"""
    get_optimization_manager().increment_async_operation()


def track_db_query():
    """追踪数据库查询"""
    get_optimization_manager().increment_db_query()


def get_optimization_status() -> Dict[str, Any]:
    """获取优化状态"""
    return get_optimization_manager().get_status()


def get_optimization_report() -> Dict[str, Any]:
    """获取优化报告"""
    return get_optimization_manager().generate_report()

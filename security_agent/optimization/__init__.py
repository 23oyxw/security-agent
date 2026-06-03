"""优化模块 - 包含所有优化相关的功能"""

from .database import DatabaseManager, get_database_manager
from .errors import AppError, handle_errors, get_error_handler
from .interfaces import ISecurityGate, IStorage, IExecutor, IMonitor
from .adapters import AdapterFactory, SecurityGateAdapter
from .cache import CacheManager, get_cache_manager, cached
from .logger import Logger, get_logger, setup_logging
from .async_io import AsyncDatabase, AsyncFileIO, AsyncTaskRunner
from .di_container import Container, get_container, inject
from .config_manager import ConfigManager, get_config_manager
from .optimization_manager import OptimizationManager, get_optimization_manager
from .health_check import HealthChecker, get_health_checker

from .realtime_sync import RealtimeSync, get_syncer, start_sync, stop_sync

__all__ = [
    # Database
    "DatabaseManager", "get_database_manager",
    # Errors
    "AppError", "handle_errors", "get_error_handler",
    # Interfaces
    "ISecurityGate", "IStorage", "IExecutor", "IMonitor",
    # Adapters
    "AdapterFactory", "SecurityGateAdapter",
    # Cache
    "CacheManager", "get_cache_manager", "cached",
    # Logger
    "Logger", "get_logger", "setup_logging",
    # Async IO
    "AsyncDatabase", "AsyncFileIO", "AsyncTaskRunner",
    # DI Container
    "Container", "get_container", "inject",
    # Config
    "ConfigManager", "get_config_manager",
    # Optimization Manager
    "OptimizationManager", "get_optimization_manager",
    # Health Check
    "HealthChecker", "get_health_checker",
    # Realtime Sync
    "RealtimeSync", "get_syncer", "start_sync", "stop_sync",
]

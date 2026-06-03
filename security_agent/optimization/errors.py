"""统一错误处理机制 - 定义系统错误类型和处理"""

from __future__ import annotations

import traceback
import functools
from typing import Any, Callable, Optional, Type, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class ErrorCode(str, Enum):
    """错误代码枚举"""
    # 通用错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    
    # 认证授权错误
    AUTH_ERROR = "AUTH_ERROR"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    
    # 资源错误
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    
    # 安全错误
    SECURITY_ERROR = "SECURITY_ERROR"
    RISK_BLOCKED = "RISK_BLOCKED"
    INTENT_MISMATCH = "INTENT_MISMATCH"
    
    # 执行错误
    EXECUTION_ERROR = "EXECUTION_ERROR"
    COMMAND_ERROR = "COMMAND_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    
    # 存储错误
    STORAGE_ERROR = "STORAGE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    
    # 外部服务错误
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    API_ERROR = "API_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"


@dataclass
class AppError(Exception):
    """应用错误基类"""
    code: ErrorCode
    message: str
    details: Optional[dict] = None
    cause: Optional[Exception] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"
    
    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class ValidationError(AppError):
    """验证错误"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details)


class SecurityError(AppError):
    """安全错误"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(ErrorCode.SECURITY_ERROR, message, details)


class RiskBlockedError(AppError):
    """风险拦截错误"""
    def __init__(self, message: str, risk_level: str = None, details: dict = None):
        details = details or {}
        if risk_level:
            details["risk_level"] = risk_level
        super().__init__(ErrorCode.RISK_BLOCKED, message, details)


class ExecutionError(AppError):
    """执行错误"""
    def __init__(self, message: str, command: str = None, details: dict = None):
        details = details or {}
        if command:
            details["command"] = command
        super().__init__(ErrorCode.EXECUTION_ERROR, message, details)


class StorageError(AppError):
    """存储错误"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(ErrorCode.STORAGE_ERROR, message, details)


class NotFoundError(AppError):
    """资源不存在错误"""
    def __init__(self, resource_type: str, resource_id: str = None):
        message = f"{resource_type}不存在"
        details = {"resource_type": resource_type, "resource_id": resource_id}
        super().__init__(ErrorCode.NOT_FOUND, message, details)


def handle_errors(func: Callable = None, *, 
                 default_return: Any = None,
                 raise_on_error: bool = False,
                 log_error: bool = True):
    """错误处理装饰器"""
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except AppError as e:
                if log_error:
                    print(f"错误: {e}")
                if raise_on_error:
                    raise
                return default_return
            except Exception as e:
                if log_error:
                    print(f"未处理错误: {type(e).__name__}: {e}")
                    traceback.print_exc()
                if raise_on_error:
                    raise AppError(
                        ErrorCode.UNKNOWN_ERROR,
                        str(e),
                        {"original_type": type(e).__name__},
                        e
                    )
                return default_return
        return wrapper
    
    if func is not None:
        return decorator(func)
    return decorator


def safe_execute(func: Callable, *args, **kwargs) -> tuple[Any, Optional[Exception]]:
    """安全执行函数，返回(结果, 错误)"""
    try:
        result = func(*args, **kwargs)
        return result, None
    except AppError as e:
        return None, e
    except Exception as e:
        return None, AppError(
            ErrorCode.UNKNOWN_ERROR,
            str(e),
            {"original_type": type(e).__name__},
            e
        )


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self._handlers = {}
        self._error_log = []
    
    def register_handler(self, error_type: Type[AppError], 
                        handler: Callable[[AppError], Any]):
        """注册错误处理器"""
        self._handlers[error_type] = handler
    
    def handle(self, error: AppError) -> Any:
        """处理错误"""
        self._error_log.append(error)
        
        for error_type, handler in self._handlers.items():
            if isinstance(error, error_type):
                return handler(error)
        
        # 默认处理
        print(f"未处理的错误: {error}")
        return None
    
    def get_error_log(self, limit: int = 100) -> list[AppError]:
        """获取错误日志"""
        return self._error_log[-limit:]


# 全局错误处理器
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler

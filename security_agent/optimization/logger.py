"""统一日志系统 - 支持多级别、多输出、结构化日志"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional, Union
from pathlib import Path
from enum import Enum


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """日志格式"""
    SIMPLE = "simple"      # 简单格式
    DETAILED = "detailed"  # 详细格式
    JSON = "json"          # JSON格式


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False)


class Logger:
    """统一日志器"""
    
    _instances: Dict[str, logging.Logger] = {}
    _log_dir: Optional[Path] = None
    _initialized = False
    
    @classmethod
    def setup(cls, 
              log_dir: str = "logs",
              level: Union[LogLevel, str] = LogLevel.INFO,
              log_format: Union[LogFormat, str] = LogFormat.DETAILED,
              max_file_size: int = 10 * 1024 * 1024,  # 10MB
              backup_count: int = 5):
        """初始化日志系统"""
        if cls._initialized:
            return
        
        cls._log_dir = Path(log_dir)
        cls._log_dir.mkdir(parents=True, exist_ok=True)
        
        # 转换级别
        if isinstance(level, LogLevel):
            level = level.value
        level = getattr(logging, level.upper())
        
        # 转换格式
        if isinstance(log_format, LogFormat):
            log_format = log_format.value
        
        # 配置根日志器
        root_logger = logging.getLogger("security_agent")
        root_logger.setLevel(level)
        
        # 清除现有处理器
        root_logger.handlers.clear()
        
        # 创建格式化器
        if log_format == "json":
            formatter = StructuredFormatter()
        elif log_format == "detailed":
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:  # simple
            formatter = logging.Formatter('%(levelname)s: %(message)s')
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            cls._log_dir / "app.log",
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 错误日志文件处理器
        error_handler = logging.handlers.RotatingFileHandler(
            cls._log_dir / "error.log",
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
        
        cls._initialized = True
    
    @classmethod
    def get_logger(cls, name: str = "security_agent") -> logging.Logger:
        """获取日志器"""
        if not cls._initialized:
            cls.setup()
        
        if name not in cls._instances:
            cls._instances[name] = logging.getLogger(name)
        
        return cls._instances[name]
    
    @classmethod
    def debug(cls, message: str, extra: Dict[str, Any] = None, logger_name: str = "security_agent"):
        """记录调试日志"""
        logger = cls.get_logger(logger_name)
        if extra:
            logger.debug(message, extra={"extra_data": extra})
        else:
            logger.debug(message)
    
    @classmethod
    def info(cls, message: str, extra: Dict[str, Any] = None, logger_name: str = "security_agent"):
        """记录信息日志"""
        logger = cls.get_logger(logger_name)
        if extra:
            logger.info(message, extra={"extra_data": extra})
        else:
            logger.info(message)
    
    @classmethod
    def warning(cls, message: str, extra: Dict[str, Any] = None, logger_name: str = "security_agent"):
        """记录警告日志"""
        logger = cls.get_logger(logger_name)
        if extra:
            logger.warning(message, extra={"extra_data": extra})
        else:
            logger.warning(message)
    
    @classmethod
    def error(cls, message: str, exc_info: bool = False, extra: Dict[str, Any] = None, logger_name: str = "security_agent"):
        """记录错误日志"""
        logger = cls.get_logger(logger_name)
        if extra:
            logger.error(message, exc_info=exc_info, extra={"extra_data": extra})
        else:
            logger.error(message, exc_info=exc_info)
    
    @classmethod
    def critical(cls, message: str, exc_info: bool = False, extra: Dict[str, Any] = None, logger_name: str = "security_agent"):
        """记录严重错误日志"""
        logger = cls.get_logger(logger_name)
        if extra:
            logger.critical(message, exc_info=exc_info, extra={"extra_data": extra})
        else:
            logger.critical(message, exc_info=exc_info)
    
    @classmethod
    def get_log_files(cls) -> list:
        """获取日志文件列表"""
        if cls._log_dir and cls._log_dir.exists():
            return [str(f) for f in cls._log_dir.glob("*.log*")]
        return []


# 便捷函数
def get_logger(name: str = "security_agent") -> logging.Logger:
    """获取日志器"""
    return Logger.get_logger(name)


def setup_logging(level: Union[LogLevel, str] = LogLevel.INFO,
                 log_format: Union[LogFormat, str] = LogFormat.DETAILED,
                 log_dir: str = "logs"):
    """初始化日志系统"""
    Logger.setup(level=level, log_format=log_format, log_dir=log_dir)


# 日志装饰器
def log_function_call(logger_name: str = "security_agent"):
    """记录函数调用的装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            func_name = func.__name__
            
            logger.debug(f"调用函数: {func_name}")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"函数 {func_name} 执行成功")
                return result
            except Exception as e:
                logger.error(f"函数 {func_name} 执行失败: {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator

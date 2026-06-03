"""配置集中管理 - 统一管理所有配置"""

from __future__ import annotations

import os
import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
from copy import deepcopy


class ConfigFormat(str, Enum):
    """配置文件格式"""
    YAML = "yaml"
    JSON = "json"
    ENV = "env"


@dataclass
class ConfigSource:
    """配置源"""
    path: str
    format: ConfigFormat
    required: bool = True
    watched: bool = False
    last_modified: float = 0


class ConfigManager:
    """配置管理器"""
    
    _instance: Optional[ConfigManager] = None
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
            self._sources: List[ConfigSource] = []
            self._config: Dict[str, Any] = {}
            self._env_prefix = "APP_"
            self._watch_enabled = False
            self._watch_interval = 5  # 秒
    
    def add_source(
        self,
        path: str,
        format: Optional[ConfigFormat] = None,
        required: bool = True
    ) -> ConfigManager:
        """添加配置源"""
        if format is None:
            # 根据文件扩展名推断格式
            ext = Path(path).suffix.lower()
            if ext in ['.yaml', '.yml']:
                format = ConfigFormat.YAML
            elif ext == '.json':
                format = ConfigFormat.JSON
            else:
                format = ConfigFormat.YAML  # 默认
        
        source = ConfigSource(path=path, format=format, required=required)
        self._sources.append(source)
        return self
    
    def set_env_prefix(self, prefix: str) -> ConfigManager:
        """设置环境变量前缀"""
        self._env_prefix = prefix
        return self
    
    def load(self) -> ConfigManager:
        """加载所有配置"""
        self._config.clear()
        
        # 按优先级加载：环境变量 > 配置文件
        # 先加载配置文件
        for source in self._sources:
            try:
                self._load_source(source)
            except Exception as e:
                if source.required:
                    raise
                print(f"警告: 加载配置文件失败 {source.path}: {e}")
        
        # 然后加载环境变量（覆盖配置文件）
        self._load_env_vars()
        
        return self
    
    def _load_source(self, source: ConfigSource):
        """加载单个配置源"""
        path = Path(source.path)
        
        if not path.exists():
            if source.required:
                raise FileNotFoundError(f"配置文件不存在: {source.path}")
            return
        
        # 更新修改时间
        source.last_modified = path.stat().st_mtime
        
        # 读取文件内容
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析配置
        if source.format == ConfigFormat.YAML:
            data = yaml.safe_load(content) or {}
        elif source.format == ConfigFormat.JSON:
            data = json.loads(content) or {}
        else:
            data = {}
        
        # 合并配置
        self._merge_config(data)
    
    def _load_env_vars(self):
        """加载环境变量"""
        env_config = {}
        
        for key, value in os.environ.items():
            # 只处理带前缀的环境变量
            if key.startswith(self._env_prefix):
                # 转换为配置键: APP_DATABASE__HOST -> database.host
                config_key = key[len(self._env_prefix):].lower()
                config_key = config_key.replace("__", ".")
                
                # 尝试解析JSON值
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass  # 保持字符串
                
                # 设置配置值
                self._set_nested_value(env_config, config_key, value)
        
        self._merge_config(env_config)
    
    def _merge_config(self, data: Dict[str, Any], prefix: str = ""):
        """合并配置"""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                self._merge_config(value, full_key)
            else:
                self._config[full_key] = value
    
    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any):
        """设置嵌套值"""
        keys = key.split(".")
        for k in keys[:-1]:
            data = data.setdefault(k, {})
        data[keys[-1]] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split(".")
        config = self._config
        
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        
        config[keys[-1]] = value
    
    def get_section(self, prefix: str) -> Dict[str, Any]:
        """获取配置段"""
        result = {}
        prefix = prefix.rstrip(".") + "."
        
        for key, value in self._config.items():
            if key.startswith(prefix):
                sub_key = key[len(prefix):]
                self._set_nested_value(result, sub_key, value)
        
        return result
    
    def has(self, key: str) -> bool:
        """检查配置是否存在"""
        return self.get(key) is not None
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return deepcopy(self._config)
    
    def reload(self) -> ConfigManager:
        """重新加载配置"""
        return self.load()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return deepcopy(self._config)
    
    def to_json(self, indent: int = 2) -> str:
        """转换为JSON字符串"""
        return json.dumps(self._config, indent=indent, ensure_ascii=False)
    
    def save(self, path: str, format: ConfigFormat = ConfigFormat.YAML):
        """保存配置到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            if format == ConfigFormat.YAML:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
            elif format == ConfigFormat.JSON:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def reset(cls):
        """重置配置管理器"""
        with cls._lock:
            cls._instance = None


# 全局配置管理器
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def load_config(config_paths: List[str] = None, env_prefix: str = "APP_") -> ConfigManager:
    """加载配置（便捷函数）"""
    manager = get_config_manager()
    manager.set_env_prefix(env_prefix)
    
    if config_paths:
        for path in config_paths:
            manager.add_source(path)
    
    return manager.load()


def get_config(key: str, default: Any = None) -> Any:
    """获取配置值（便捷函数）"""
    return get_config_manager().get(key, default)


def set_config(key: str, value: Any):
    """设置配置值（便捷函数）"""
    get_config_manager().set(key, value)

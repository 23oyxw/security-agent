"""插件管理界面 - 管理和监控MCP插件，支持动态发现."""

from __future__ import annotations

import json
import os
import sqlite3
import importlib
import inspect
import pkgutil
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PluginStatus(str, Enum):
    """插件状态"""
    ACTIVE = "active"      # 活跃
    INACTIVE = "inactive"  # 未激活
    ERROR = "error"        # 错误
    DISABLED = "disabled"  # 已禁用


class PluginType(str, Enum):
    """插件类型"""
    TOOL = "tool"          # 工具插件
    SKILL = "skill"        # 技能插件
    INTEGRATION = "integration"  # 集成插件
    MONITOR = "monitor"    # 监控插件


@dataclass
class PluginInfo:
    """插件信息"""
    plugin_id: str
    name: str
    type: PluginType
    status: PluginStatus
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    entry_file: str = ""
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    usage_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "entry_file": self.entry_file,
            "dependencies": self.dependencies,
            "config": self.config,
            "registered_at": self.registered_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "error_count": self.error_count,
            "last_error": self.last_error
        }


class PluginManager:
    """插件管理器"""
    
    def __init__(self, db_path: str = "data/plugins.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._plugins: Dict[str, PluginInfo] = {}
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plugins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    type TEXT,
                    status TEXT,
                    version TEXT,
                    description TEXT,
                    author TEXT,
                    entry_file TEXT,
                    dependencies TEXT,
                    config TEXT,
                    registered_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    usage_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT
                )
            """)
            conn.commit()
    
    def register_plugin(self, plugin_info: PluginInfo) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO plugins 
                       (plugin_id, name, type, status, version, description, author, 
                        entry_file, dependencies, config, registered_at, updated_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (plugin_info.plugin_id, plugin_info.name, plugin_info.type.value,
                     plugin_info.status.value, plugin_info.version, plugin_info.description,
                     plugin_info.author, plugin_info.entry_file, 
                     json.dumps(plugin_info.dependencies), json.dumps(plugin_info.config),
                     plugin_info.registered_at, plugin_info.updated_at)
                )
                conn.commit()
            
            self._plugins[plugin_info.plugin_id] = plugin_info
            return True
        except Exception as e:
            print(f"注册插件失败: {e}")
            return False
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        return self._plugins.get(plugin_id)
    
    def list_plugins(self, plugin_type: PluginType = None, 
                    status: PluginStatus = None) -> List[PluginInfo]:
        plugins = list(self._plugins.values())
        
        if plugin_type:
            plugins = [p for p in plugins if p.type == plugin_type]
        
        if status:
            plugins = [p for p in plugins if p.status == status]
        
        return plugins
    
    def get_plugin_statistics(self) -> Dict[str, Any]:
        total_plugins = len(self._plugins)
        
        type_stats = {}
        for plugin_type in PluginType:
            count = len([p for p in self._plugins.values() if p.type == plugin_type])
            type_stats[plugin_type.value] = count
        
        status_stats = {}
        for status in PluginStatus:
            count = len([p for p in self._plugins.values() if p.status == status])
            status_stats[status.value] = count
        
        total_usage = sum(p.usage_count for p in self._plugins.values())
        total_errors = sum(p.error_count for p in self._plugins.values())
        
        return {
            "total_plugins": total_plugins,
            "type_stats": type_stats,
            "status_stats": status_stats,
            "total_usage": total_usage,
            "total_errors": total_errors
        }


    def discover_plugins(self, package_path: str, package_name: str) -> List[PluginInfo]:
        """动态发现插件模块.

        扫描指定包路径下所有模块，查找带有 __plugin_info__ 属性或继承自 BasePlugin 的类。

        Args:
            package_path: 包的文件系统路径（如 security_agent/plugins）
            package_name: 包的导入名（如 security_agent.plugins）

        Returns:
            发现并注册的插件列表
        """
        discovered: List[PluginInfo] = []
        pkg_path = Path(package_path)

        if not pkg_path.is_dir():
            return discovered

        for importer, module_name, is_pkg in pkgutil.iter_modules([str(pkg_path)]):
            if module_name.startswith("_"):
                continue

            full_name = f"{package_name}.{module_name}"
            try:
                module = importlib.import_module(full_name)
            except Exception as e:
                print(f"导入插件模块 {full_name} 失败: {e}")
                continue

            # 方式1: 检查模块级 __plugin_info__ 字典
            plugin_info_dict = getattr(module, "__plugin_info__", None)
            if isinstance(plugin_info_dict, dict):
                info = PluginInfo(
                    plugin_id=plugin_info_dict.get("plugin_id", module_name),
                    name=plugin_info_dict.get("name", module_name),
                    type=PluginType(plugin_info_dict.get("type", "tool")),
                    status=PluginStatus(plugin_info_dict.get("status", "active")),
                    version=plugin_info_dict.get("version", "1.0.0"),
                    description=plugin_info_dict.get("description", ""),
                    author=plugin_info_dict.get("author", ""),
                    entry_file=full_name,
                    dependencies=plugin_info_dict.get("dependencies", []),
                    config=plugin_info_dict.get("config", {}),
                )
                self.register_plugin(info)
                discovered.append(info)
                continue

            # 方式2: 扫描模块中的类，查找带 plugin_id 或 get_plugin_info 的类
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ != full_name:
                    continue

                get_info_fn = getattr(obj, "get_plugin_info", None)
                if callable(get_info_fn):
                    try:
                        info_dict = get_info_fn()
                        if isinstance(info_dict, dict):
                            info = PluginInfo(
                                plugin_id=info_dict.get("plugin_id", f"{module_name}.{name}"),
                                name=info_dict.get("name", name),
                                type=PluginType(info_dict.get("type", "tool")),
                                status=PluginStatus(info_dict.get("status", "active")),
                                version=info_dict.get("version", "1.0.0"),
                                description=info_dict.get("description", ""),
                                author=info_dict.get("author", ""),
                                entry_file=full_name,
                                dependencies=info_dict.get("dependencies", []),
                                config=info_dict.get("config", {}),
                            )
                            self.register_plugin(info)
                            discovered.append(info)
                    except Exception:
                        pass

                # 方式3: 类属性中有 plugin_id
                elif hasattr(obj, "plugin_id") and isinstance(getattr(obj, "plugin_id", None), str):
                    info = PluginInfo(
                        plugin_id=getattr(obj, "plugin_id"),
                        name=getattr(obj, "plugin_name", name),
                        type=PluginType(getattr(obj, "plugin_type", "tool")),
                        status=PluginStatus.ACTIVE,
                        version=getattr(obj, "plugin_version", "1.0.0"),
                        description=getattr(obj, "plugin_description", ""),
                        author=getattr(obj, "plugin_author", ""),
                        entry_file=full_name,
                    )
                    self.register_plugin(info)
                    discovered.append(info)

        return discovered

    def activate_plugin(self, plugin_id: str) -> bool:
        """激活指定插件."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        plugin.status = PluginStatus.ACTIVE
        plugin.updated_at = datetime.now().isoformat()
        self._update_db_status(plugin_id, PluginStatus.ACTIVE)
        return True

    def deactivate_plugin(self, plugin_id: str) -> bool:
        """停用指定插件."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        plugin.status = PluginStatus.INACTIVE
        plugin.updated_at = datetime.now().isoformat()
        self._update_db_status(plugin_id, PluginStatus.INACTIVE)
        return True

    def record_usage(self, plugin_id: str, success: bool = True, error_msg: str = "") -> None:
        """记录插件使用情况."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return
        plugin.usage_count += 1
        if not success:
            plugin.error_count += 1
            plugin.last_error = error_msg
            plugin.updated_at = datetime.now().isoformat()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """UPDATE plugins SET usage_count = ?, error_count = ?, last_error = ?, updated_at = ?
                       WHERE plugin_id = ?""",
                    (plugin.usage_count, plugin.error_count, plugin.last_error,
                     plugin.updated_at, plugin_id)
                )
                conn.commit()
        except Exception:
            pass

    def load_plugins_from_db(self) -> int:
        """从数据库加载已注册的插件信息.

        Returns:
            加载的插件数量
        """
        count = 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM plugins").fetchall()
                for row in rows:
                    try:
                        info = PluginInfo(
                            plugin_id=row["plugin_id"],
                            name=row["name"],
                            type=PluginType(row["type"]),
                            status=PluginStatus(row["status"]),
                            version=row["version"] or "1.0.0",
                            description=row["description"] or "",
                            author=row["author"] or "",
                            entry_file=row["entry_file"] or "",
                            dependencies=json.loads(row["dependencies"]) if row["dependencies"] else [],
                            config=json.loads(row["config"]) if row["config"] else {},
                            registered_at=row["registered_at"] or datetime.now().isoformat(),
                            updated_at=row["updated_at"] or datetime.now().isoformat(),
                            usage_count=row["usage_count"] or 0,
                            error_count=row["error_count"] or 0,
                            last_error=row["last_error"],
                        )
                        self._plugins[info.plugin_id] = info
                        count += 1
                    except (ValueError, KeyError):
                        continue
        except Exception:
            pass
        return count

    def _update_db_status(self, plugin_id: str, status: PluginStatus) -> None:
        """更新数据库中插件状态."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE plugins SET status = ?, updated_at = ? WHERE plugin_id = ?",
                    (status.value, datetime.now().isoformat(), plugin_id)
                )
                conn.commit()
        except Exception:
            pass

    def get_plugin_health(self) -> Dict[str, Any]:
        """获取插件健康概览."""
        total = len(self._plugins)
        active = len([p for p in self._plugins.values() if p.status == PluginStatus.ACTIVE])
        error = len([p for p in self._plugins.values() if p.status == PluginStatus.ERROR])
        inactive = len([p for p in self._plugins.values() if p.status == PluginStatus.INACTIVE])
        total_errors = sum(p.error_count for p in self._plugins.values())
        total_usage = sum(p.usage_count for p in self._plugins.values())

        error_rate = total_errors / total_usage if total_usage > 0 else 0.0

        return {
            "total": total,
            "active": active,
            "error": error,
            "inactive": inactive,
            "total_usage": total_usage,
            "total_errors": total_errors,
            "error_rate": round(error_rate, 4),
            "health_score": round(max(0, 1.0 - error_rate) * 100, 1),
        }


# 全局单例
_plugin_manager_instance: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    global _plugin_manager_instance
    if _plugin_manager_instance is None:
        _plugin_manager_instance = PluginManager()
    return _plugin_manager_instance

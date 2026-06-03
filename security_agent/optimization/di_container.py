"""依赖注入容器 - 管理模块依赖和生命周期"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Type, Callable, Union
from enum import Enum
from dataclasses import dataclass
from contextlib import contextmanager


class Lifecycle(str, Enum):
    """生命周期类型"""
    SINGLETON = "singleton"  # 单例
    TRANSIENT = "transient"  # 每次新建
    SCOPED = "scoped"        # 作用域内单例


@dataclass
class ServiceDescriptor:
    """服务描述符"""
    interface: Type
    implementation: Optional[Type] = None
    factory: Optional[Callable] = None
    lifecycle: Lifecycle = Lifecycle.SINGLETON
    instance: Any = None
    dependencies: List[Type] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class Container:
    """依赖注入容器"""
    
    _instance: Optional[Container] = None
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
            self._services: Dict[Type, ServiceDescriptor] = {}
            self._named_services: Dict[str, ServiceDescriptor] = {}
            self._scoped_instances: Dict[str, Dict[Type, Any]] = {}
            self._current_scope: Optional[str] = None
    
    def register(
        self,
        interface: Type,
        implementation: Optional[Type] = None,
        *,
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
        factory: Optional[Callable] = None,
        name: Optional[str] = None
    ) -> Container:
        """注册服务"""
        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation or interface,
            lifecycle=lifecycle,
            factory=factory
        )
        
        if name:
            self._named_services[name] = descriptor
        else:
            self._services[interface] = descriptor
        
        return self
    
    def register_instance(self, interface: Type, instance: Any, name: Optional[str] = None) -> Container:
        """注册实例"""
        descriptor = ServiceDescriptor(
            interface=interface,
            lifecycle=Lifecycle.SINGLETON,
            instance=instance
        )
        
        if name:
            self._named_services[name] = descriptor
        else:
            self._services[interface] = descriptor
        
        return self
    
    def register_factory(
        self,
        interface: Type,
        factory: Callable,
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
        name: Optional[str] = None
    ) -> Container:
        """注册工厂"""
        descriptor = ServiceDescriptor(
            interface=interface,
            lifecycle=lifecycle,
            factory=factory
        )
        
        if name:
            self._named_services[name] = descriptor
        else:
            self._services[interface] = descriptor
        
        return self
    
    def resolve(self, interface: Type, name: Optional[str] = None) -> Any:
        """解析服务"""
        descriptor = None
        
        if name:
            descriptor = self._named_services.get(name)
        
        if descriptor is None:
            descriptor = self._services.get(interface)
        
        if descriptor is None:
            raise ValueError(f"服务未注册: {interface.__name__}")
        
        # 单例模式
        if descriptor.lifecycle == Lifecycle.SINGLETON:
            if descriptor.instance is None:
                descriptor.instance = self._create_instance(descriptor)
            return descriptor.instance
        
        # 作用域模式
        if descriptor.lifecycle == Lifecycle.SCOPED:
            if self._current_scope is None:
                raise RuntimeError("没有活跃的作用域")
            
            scope_dict = self._scoped_instances.setdefault(self._current_scope, {})
            if interface not in scope_dict:
                scope_dict[interface] = self._create_instance(descriptor)
            return scope_dict[interface]
        
        # 瞬态模式
        return self._create_instance(descriptor)
    
    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """创建实例"""
        if descriptor.instance is not None:
            return descriptor.instance
        
        if descriptor.factory:
            return descriptor.factory(self)
        
        # 自动注入依赖
        implementation = descriptor.implementation
        if implementation is None:
            implementation = descriptor.interface
        
        # 检查__init__参数
        init_method = getattr(implementation, '__init__', None)
        if init_method and hasattr(init_method, '__annotations__'):
            annotations = init_method.__annotations__
            params = {}
            for param_name, param_type in annotations.items():
                if param_name == 'return':
                    continue
                try:
                    params[param_name] = self.resolve(param_type)
                except ValueError:
                    # 依赖未注册，尝试使用None
                    params[param_name] = None
            
            return implementation(**params)
        
        return implementation()
    
    @contextmanager
    def scope(self, scope_name: str = "default"):
        """创建作用域"""
        old_scope = self._current_scope
        self._current_scope = scope_name
        try:
            yield self
        finally:
            # 清理作用域实例
            if scope_name in self._scoped_instances:
                del self._scoped_instances[scope_name]
            self._current_scope = old_scope
    
    def is_registered(self, interface: Type, name: Optional[str] = None) -> bool:
        """检查服务是否已注册"""
        if name:
            return name in self._named_services
        return interface in self._services
    
    def get_registered_services(self) -> List[Type]:
        """获取已注册的服务列表"""
        return list(self._services.keys())
    
    def get_named_services(self) -> List[str]:
        """获取已注册的命名服务列表"""
        return list(self._named_services.keys())
    
    def clear(self):
        """清空容器"""
        self._services.clear()
        self._named_services.clear()
        self._scoped_instances.clear()
    
    @classmethod
    def reset(cls):
        """重置容器（主要用于测试）"""
        with cls._lock:
            cls._instance = None


# 全局容器
_container: Optional[Container] = None


def get_container() -> Container:
    """获取全局容器"""
    global _container
    if _container is None:
        _container = Container()
    return _container


def register_service(interface: Type, implementation: Optional[Type] = None, **kwargs) -> Container:
    """注册服务（便捷函数）"""
    return get_container().register(interface, implementation, **kwargs)


def resolve_service(interface: Type, name: Optional[str] = None) -> Any:
    """解析服务（便捷函数）"""
    return get_container().resolve(interface, name)


def inject(interface: Type):
    """依赖注入装饰器"""
    def decorator(cls):
        original_init = cls.__init__
        
        def new_init(self, *args, **kwargs):
            container = get_container()
            # 检查是否有未提供的参数
            init_method = getattr(cls, '__init__', None)
            if init_method and hasattr(init_method, '__annotations__'):
                annotations = init_method.__annotations__
                for param_name, param_type in annotations.items():
                    if param_name == 'return':
                        continue
                    if param_name not in kwargs:
                        try:
                            kwargs[param_name] = container.resolve(param_type)
                        except ValueError:
                            pass  # 依赖未注册，保持原样
            
            original_init(self, *args, **kwargs)
        
        cls.__init__ = new_init
        return cls
    
    return decorator


class DependencyTracker:
    """依赖追踪器 - 用于调试和可视化"""
    
    def __init__(self):
        self._resolutions: List[Dict[str, Any]] = []
    
    def track(self, interface: Type, instance: Any, source: str = "resolve"):
        """追踪解析"""
        self._resolutions.append({
            "interface": interface.__name__,
            "instance_type": type(instance).__name__,
            "source": source,
            "timestamp": __import__('time').time()
        })
    
    def get_resolutions(self) -> List[Dict[str, Any]]:
        """获取解析记录"""
        return self._resolutions.copy()
    
    def clear(self):
        """清空记录"""
        self._resolutions.clear()

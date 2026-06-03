"""统一缓存机制 - 支持内存缓存和TTL过期"""

from __future__ import annotations

import time
import threading
import hashlib
import json
from typing import Any, Optional, Callable, Dict, Tuple
from functools import wraps
from dataclasses import dataclass, field
from collections import OrderedDict


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    created_at: float
    ttl: float  # 生存时间（秒）
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    @property
    def is_expired(self) -> bool:
        """是否过期"""
        if self.ttl <= 0:  # ttl <= 0 表示永不过期
            return False
        return time.time() - self.created_at > self.ttl
    
    def access(self) -> Any:
        """访问缓存，更新访问统计"""
        self.access_count += 1
        self.last_access = time.time()
        return self.value


class LRUCache:
    """LRU缓存 - 基于有序字典实现"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            
            entry = self._cache[key]
            
            # 检查是否过期
            if entry.is_expired:
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return entry.access()
    
    def set(self, key: str, value: Any, ttl: float = 300) -> bool:
        """设置缓存值"""
        with self._lock:
            # 如果key已存在，先删除
            if key in self._cache:
                del self._cache[key]
            
            # 检查容量，删除最久未使用的
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1
            
            # 添加新条目
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl
            )
            self._cache[key] = entry
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)
    
    @property
    def size(self) -> int:
        """当前缓存大小"""
        return len(self._cache)
    
    @property
    def stats(self) -> dict:
        """缓存统计"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
            return {
                "size": self.size,
                "max_size": self.max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": round(hit_rate, 2),
                "evictions": self._stats["evictions"]
            }


class CacheManager:
    """缓存管理器 - 管理多个缓存实例"""
    
    _instance: Optional[CacheManager] = None
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
            self._caches: Dict[str, LRUCache] = {}
            self._default_ttl = 300  # 默认5分钟
            self._cleanup_interval = 60  # 清理间隔60秒
            self._last_cleanup = time.time()
    
    def get_cache(self, namespace: str, max_size: int = 1000) -> LRUCache:
        """获取或创建缓存实例"""
        if namespace not in self._caches:
            self._caches[namespace] = LRUCache(max_size)
        return self._caches[namespace]
    
    def get(self, namespace: str, key: str) -> Optional[Any]:
        """获取缓存值"""
        cache = self.get_cache(namespace)
        
        # 定期清理过期缓存
        if time.time() - self._last_cleanup > self._cleanup_interval:
            cache.cleanup_expired()
            self._last_cleanup = time.time()
        
        return cache.get(key)
    
    def set(self, namespace: str, key: str, value: Any, ttl: float = None) -> bool:
        """设置缓存值"""
        cache = self.get_cache(namespace)
        ttl = ttl if ttl is not None else self._default_ttl
        return cache.set(key, value, ttl)
    
    def delete(self, namespace: str, key: str) -> bool:
        """删除缓存"""
        if namespace in self._caches:
            return self._caches[namespace].delete(key)
        return False
    
    def clear(self, namespace: str = None):
        """清空缓存"""
        if namespace:
            if namespace in self._caches:
                self._caches[namespace].clear()
        else:
            for cache in self._caches.values():
                cache.clear()
    
    def get_stats(self, namespace: str = None) -> dict:
        """获取缓存统计"""
        if namespace:
            if namespace in self._caches:
                return self._caches[namespace].stats
            return {}
        
        stats = {}
        for ns, cache in self._caches.items():
            stats[ns] = cache.stats
        return stats


# 全局缓存管理器
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cached(namespace: str = "default", ttl: float = 300, key_prefix: str = ""):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_mgr = get_cache_manager()
            
            # 生成缓存key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()
            
            # 尝试从缓存获取
            cached_value = cache_mgr.get(namespace, cache_key)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            cache_mgr.set(namespace, cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def cache_key(*args, **kwargs) -> str:
    """生成缓存key"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.md5("|".join(key_parts).encode()).hexdigest()

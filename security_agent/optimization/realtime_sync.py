"""实时状态同步器 - 提供数据的实时更新功能"""

from __future__ import annotations

import time
import threading
from typing import Any, Dict, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SyncUpdate:
    """同步更新数据"""
    timestamp: float
    data: Dict[str, Any]
    event_type: str = "update"
    

class RealtimeSync:
    """实时同步器"""
    
    def __init__(self, update_interval: float = 2.0):
        self.update_interval = update_interval
        self._callbacks: Dict[str, Callable] = {}
        self._last_data: Dict[str, Any] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
    def register_callback(self, name: str, callback: Callable):
        """注册回调函数"""
        self._callbacks[name] = callback
        
    def unregister_callback(self, name: str):
        """取消注册回调"""
        if name in self._callbacks:
            del self._callbacks[name]
    
    def start(self):
        """启动同步"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        
    def stop(self):
        """停止同步"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            
    def _sync_loop(self):
        """同步循环"""
        while self._running:
            try:
                self._sync_all()
            except Exception as e:
                print(f"同步错误: {e}")
            time.sleep(self.update_interval)
            
    def _sync_all(self):
        """同步所有数据"""
        with self._lock:
            for name, callback in self._callbacks.items():
                try:
                    new_data = callback()
                    if new_data != self._last_data.get(name):
                        self._last_data[name] = new_data
                        # 可以在这里触发事件
                except Exception as e:
                    print(f"回调 {name} 执行失败: {e}")
    
    def get_data(self, name: str) -> Optional[Dict[str, Any]]:
        """获取数据"""
        return self._last_data.get(name)
    
    def get_all_data(self) -> Dict[str, Any]:
        """获取所有数据"""
        return dict(self._last_data)


# 全局同步器
_syncer: Optional[RealtimeSync] = None


def get_syncer() -> RealtimeSync:
    """获取全局同步器"""
    global _syncer
    if _syncer is None:
        _syncer = RealtimeSync()
    return _syncer


def start_sync():
    """启动全局同步"""
    get_syncer().start()


def stop_sync():
    """停止全局同步"""
    get_syncer().stop()


def register_sync_callback(name: str, callback: Callable):
    """注册同步回调"""
    get_syncer().register_callback(name, callback)


def get_sync_data(name: str) -> Optional[Dict[str, Any]]:
    """获取同步数据"""
    return get_syncer().get_data(name)

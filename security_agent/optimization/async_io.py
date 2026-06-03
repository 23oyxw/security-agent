"""异步IO操作模块 - 使用线程池实现异步IO"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional, Callable, List
from contextlib import asynccontextmanager
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import time
import json
import sqlite3
import os


@dataclass
class AsyncIOResult:
    """异步IO结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    elapsed_time: float = 0.0
    
    def __bool__(self):
        return self.success


class ThreadPool:
    """线程池管理器"""
    
    _instance: Optional[ThreadPool] = None
    _executor: Optional[ThreadPoolExecutor] = None
    
    @classmethod
    def get_executor(cls) -> ThreadPoolExecutor:
        """获取线程池执行器"""
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=8)
        return cls._executor
    
    @classmethod
    def shutdown(cls):
        """关闭线程池"""
        if cls._executor:
            cls._executor.shutdown(wait=True)


class AsyncDatabase:
    """异步数据库操作器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def execute(self, query: str, params: tuple = ()) -> AsyncIOResult:
        """执行查询"""
        start_time = time.time()
        
        def _execute():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(ThreadPool.get_executor(), _execute)
            elapsed = time.time() - start_time
            return AsyncIOResult(True, result, elapsed_time=elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            return AsyncIOResult(False, error=str(e), elapsed_time=elapsed)
    
    async def fetch_one(self, query: str, params: tuple = ()) -> AsyncIOResult:
        """获取单条记录"""
        start_time = time.time()
        
        def _fetch():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(ThreadPool.get_executor(), _fetch)
            elapsed = time.time() - start_time
            return AsyncIOResult(True, result, elapsed_time=elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            return AsyncIOResult(False, error=str(e), elapsed_time=elapsed)
    
    async def fetch_all(self, query: str, params: tuple = ()) -> AsyncIOResult:
        """获取所有记录"""
        start_time = time.time()
        
        def _fetch():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(ThreadPool.get_executor(), _fetch)
            elapsed = time.time() - start_time
            return AsyncIOResult(True, result, elapsed_time=elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            return AsyncIOResult(False, error=str(e), elapsed_time=elapsed)
    
    async def execute_many(self, query: str, params_list: List[tuple]) -> AsyncIOResult:
        """批量执行"""
        start_time = time.time()
        
        def _execute():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(ThreadPool.get_executor(), _execute)
            elapsed = time.time() - start_time
            return AsyncIOResult(True, result, elapsed_time=elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            return AsyncIOResult(False, error=str(e), elapsed_time=elapsed)


class AsyncFileIO:
    """异步文件IO操作器"""
    
    @staticmethod
    async def read_text(file_path: str, encoding: str = "utf-8") -> AsyncIOResult:
        """异步读取文本文件"""
        start_time = time.time()
        
        def _read():
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        
        try:
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(ThreadPool.get_executor(), _read)
            elapsed = time.time() - start_time
            return AsyncIOResult(True, content, elapsed_time=elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            return AsyncIOResult(False, error=str(e), elapsed_time=elapsed)
    
    @staticmethod
    async def write_text(file_path: str, content: str, encoding: str = "utf-8") -> AsyncIOResult:
        """异步写入文本文件"""
        start_time = time.time()
        
        def _write():
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            return True
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(ThreadPool.get_executor(), _write)
            elapsed = time.time() - start_time
            return AsyncIOResult(True, True, elapsed_time=elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            return AsyncIOResult(False, error=str(e), elapsed_time=elapsed)
    
    @staticmethod
    async def read_json(file_path: str) -> AsyncIOResult:
        """异步读取JSON文件"""
        result = await AsyncFileIO.read_text(file_path)
        if result.success:
            try:
                data = json.loads(result.data)
                return AsyncIOResult(True, data, elapsed_time=result.elapsed_time)
            except json.JSONDecodeError as e:
                return AsyncIOResult(False, error=str(e), elapsed_time=result.elapsed_time)
        return result
    
    @staticmethod
    async def write_json(file_path: str, data: Any, indent: int = 2) -> AsyncIOResult:
        """异步写入JSON文件"""
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        return await AsyncFileIO.write_text(file_path, content)
    
    @staticmethod
    def exists(file_path: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(file_path)
    
    @staticmethod
    async def delete(file_path: str) -> AsyncIOResult:
        """异步删除文件"""
        start_time = time.time()
        
        def _delete():
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(ThreadPool.get_executor(), _delete)
            elapsed = time.time() - start_time
            return AsyncIOResult(True, True, elapsed_time=elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            return AsyncIOResult(False, error=str(e), elapsed_time=elapsed)


def async_retry(max_attempts: int = 3, delay: float = 1.0):
    """异步重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay * (attempt + 1))
            raise last_error
        return wrapper
    return decorator


@asynccontextmanager
async def async_timer(operation_name: str = "operation"):
    """异步计时器上下文管理器"""
    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        print(f"[AsyncTimer] {operation_name} 耗时: {elapsed:.3f}秒")


class AsyncTaskRunner:
    """异步任务运行器"""
    
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self._semaphore = None
    
    def _get_semaphore(self):
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore
    
    async def run_task(self, task: Callable, *args, **kwargs) -> Any:
        """运行单个任务"""
        async with self._get_semaphore():
            if asyncio.iscoroutinefunction(task):
                return await task(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(ThreadPool.get_executor(), task, *args, **kwargs)
    
    async def run_tasks(self, tasks: List[Callable], args_list: List[tuple] = None) -> List[Any]:
        """批量运行任务"""
        args_list = args_list or [() for _ in tasks]
        async_tasks = []
        for i, task in enumerate(tasks):
            args = args_list[i] if i < len(args_list) else ()
            async_tasks.append(self.run_task(task, *args))
        
        return await asyncio.gather(*async_tasks, return_exceptions=True)


# 便捷函数
def run_async(coro):
    """运行异步函数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.create_task(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)

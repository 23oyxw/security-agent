"""并行执行模块 — 对独立只读操作使用 asyncio.gather 提速.

适用场景：
- 多个独立的只读安全扫描（进程、端口、系统状态）
- 批量信息收集（无依赖关系）
- 并行知识库检索

不适用场景：
- 有状态依赖的操作（如先扫描再基于结果拦截）
- 写操作（kill/block/修改配置）
- 需要严格顺序的规划任务
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from security_agent.tools.registry import call_tool_local


# 定义为安全可并行的只读工具
PARALLEL_SAFE_TOOLS = frozenset({
    "query_security_scan",
    "query_security_scan_json",
    "list_processes",
    "get_system_health",
    "list_network_connections",
    "check_sensitive_paths",
    "check_exposed_ports",
    "get_monitor_events",
    "get_audit_log",
    "search_security_knowledge",
})


async def run_tools_parallel(
    tool_calls: list[tuple[str, dict[str, Any]]],
    max_concurrency: int = 5,
    wall_timeout_sec: float | None = None,
) -> dict[str, Any]:
    """并行执行多个工具调用.

    Args:
        tool_calls: 工具调用列表，每项为 (tool_name, arguments)
        max_concurrency: 最大并发数，防止过多请求压垮 API

    Returns:
        执行结果字典，包含 results、errors、timing 信息
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _call_with_semaphore(name: str, args: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            start = asyncio.get_event_loop().time()
            try:
                result = await call_tool_local(name, args)
                return {
                    "tool": name,
                    "success": True,
                    "result": result,
                    "duration_ms": round((asyncio.get_event_loop().time() - start) * 1000, 2),
                }
            except Exception as exc:
                return {
                    "tool": name,
                    "success": False,
                    "error": str(exc),
                    "duration_ms": round((asyncio.get_event_loop().time() - start) * 1000, 2),
                }

    from security_agent.resilience.budget import get_request_budget

    if wall_timeout_sec is None:
        budget = get_request_budget()
        if budget:
            wall_timeout_sec = budget.slice_timeout("tools")

    tasks = [_call_with_semaphore(name, args) for name, args in tool_calls]
    if wall_timeout_sec:
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=wall_timeout_sec,
            )
        except asyncio.TimeoutError:
            return {
                "parallel": True,
                "total": len(tool_calls),
                "successful": 0,
                "failed": len(tool_calls),
                "results": {},
                "errors": {"_wall": f"parallel wall timeout {wall_timeout_sec}s"},
                "timing": {},
            }
    else:
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # 整理结果
    output = {
        "parallel": True,
        "total": len(tool_calls),
        "successful": 0,
        "failed": 0,
        "results": {},
        "errors": {},
        "timing": {},
    }

    for r in results:
        if isinstance(r, Exception):
            output["failed"] += 1
            output["errors"][f"unknown_{len(output['errors'])}"] = str(r)
            continue

        tool_name = r["tool"]
        output["timing"][tool_name] = r.get("duration_ms", 0)

        if r.get("success"):
            output["successful"] += 1
            output["results"][tool_name] = r.get("result", "")
        else:
            output["failed"] += 1
            output["errors"][tool_name] = r.get("error", "Unknown error")

    return output


async def run_security_info_gathering(
    include_scan: bool = True,
    include_processes: bool = True,
    include_health: bool = True,
    include_network: bool = True,
    include_ports: bool = True,
) -> dict[str, Any]:
    """并行收集系统安全信息 — 一键综合信息采集.

    并行执行多个独立的只读安全扫描，提速响应。

    Args:
        include_scan: 是否包含安全扫描
        include_processes: 是否包含进程列表
        include_health: 是否包含系统健康
        include_network: 是否包含网络连接
        include_ports: 是否包含端口检查

    Returns:
        包含所有结果的字典
    """
    tool_calls: list[tuple[str, dict[str, Any]]] = []

    if include_scan:
        tool_calls.append(("query_security_scan_json", {}))
    if include_processes:
        tool_calls.append(("list_processes", {"limit": 50}))
    if include_health:
        tool_calls.append(("get_system_health", {}))
    if include_network:
        tool_calls.append(("list_network_connections", {"limit": 30}))
    if include_ports:
        tool_calls.append(("check_exposed_ports", {}))

    if not tool_calls:
        return {"parallel": True, "results": {}, "message": "未选择任何采集项"}

    result = await run_tools_parallel(tool_calls, max_concurrency=len(tool_calls))

    # 添加综合摘要
    summary_parts = []
    if "query_security_scan_json" in result.get("results", {}):
        summary_parts.append("✓ 安全扫描")
    if "list_processes" in result.get("results", {}):
        summary_parts.append("✓ 进程信息")
    if "get_system_health" in result.get("results", {}):
        summary_parts.append("✓ 系统健康")
    if "list_network_connections" in result.get("results", {}):
        summary_parts.append("✓ 网络连接")
    if "check_exposed_ports" in result.get("results", {}):
        summary_parts.append("✓ 端口检查")

    result["summary"] = f"并行采集完成: {' | '.join(summary_parts)}"
    result["total_time_ms"] = sum(result.get("timing", {}).values())

    return result


def is_tool_parallel_safe(tool_name: str) -> bool:
    """检查工具是否可以安全并行执行.

    Args:
        tool_name: 工具名称

    Returns:
        是否可以并行
    """
    return tool_name in PARALLEL_SAFE_TOOLS


async def run_with_fallback(
    primary_tool: str,
    fallback_tools: list[str],
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """并行执行主工具和备选工具，返回最快成功的结果.

    用于时效性要求高的场景，如监控告警触发时的快速诊断。

    Args:
        primary_tool: 主工具
        fallback_tools: 备选工具列表（按优先级排序）
        args: 工具参数

    Returns:
        执行结果
    """
    args = args or {}
    all_tools = [primary_tool] + fallback_tools

    tool_calls = [(name, args) for name in all_tools]
    result = await run_tools_parallel(tool_calls, max_concurrency=len(tool_calls))

    # 找到第一个成功的结果
    for tool_name in all_tools:
        if tool_name in result.get("results", {}):
            return {
                "tool_used": tool_name,
                "result": result["results"][tool_name],
                "parallel_results": result,
                "fallback_used": tool_name != primary_tool,
            }

    # 全部失败
    return {
        "tool_used": None,
        "result": None,
        "error": result.get("errors", {}),
        "parallel_results": result,
    }


class ParallelExecutor:
    """并行执行器 — 用于需要批量并发执行的场景."""

    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency
        self._results_cache: dict[str, Any] = {}

    async def execute_batch(
        self,
        tasks: list[dict[str, Any]],
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """批量执行任务.

        Args:
            tasks: 任务列表，每项为 {"tool": str, "args": dict, "id": str}
            use_cache: 是否使用缓存

        Returns:
            执行结果列表
        """
        # 去重（基于 cache key）
        unique_calls: list[tuple[str, dict[str, Any], str]] = []
        cache_map: dict[str, str] = {}  # cache_key -> task_id

        for task in tasks:
            tool = task["tool"]
            args = task.get("args", {})
            task_id = task.get("id", f"task_{len(unique_calls)}")

            cache_key = f"{tool}:{json.dumps(args, sort_keys=True)}"

            if use_cache and cache_key in self._results_cache:
                cache_map[task_id] = cache_key
            else:
                unique_calls.append((tool, args, task_id))
                if use_cache:
                    cache_map[task_id] = cache_key

        # 并行执行去重后的任务
        if unique_calls:
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def _exec(tool: str, args: dict[str, Any], task_id: str) -> dict[str, Any]:
                async with semaphore:
                    result = await call_tool_local(tool, args)
                    cache_key = cache_map.get(task_id)
                    if cache_key and use_cache:
                        self._results_cache[cache_key] = result
                    return {
                        "id": task_id,
                        "tool": tool,
                        "result": result,
                        "from_cache": False,
                    }

            exec_results = await asyncio.gather(
                *[_exec(t, a, i) for t, a, i in unique_calls],
                return_exceptions=True,
            )

            # 处理异常
            processed_results: dict[str, dict[str, Any]] = {}
            for r in exec_results:
                if isinstance(r, Exception):
                    # 找到对应的 task_id
                    task_id = str(r)  # fallback
                    processed_results[task_id] = {
                        "id": task_id,
                        "error": str(r),
                        "from_cache": False,
                    }
                else:
                    processed_results[r["id"]] = r
        else:
            processed_results = {}

        # 组装最终结果（包含缓存命中）
        final_results = []
        for task in tasks:
            task_id = task.get("id", "")
            cache_key = cache_map.get(task_id)

            if cache_key and cache_key in self._results_cache:
                # 缓存命中
                final_results.append({
                    "id": task_id,
                    "tool": task["tool"],
                    "result": self._results_cache[cache_key],
                    "from_cache": True,
                })
            elif task_id in processed_results:
                final_results.append(processed_results[task_id])
            else:
                final_results.append({
                    "id": task_id,
                    "error": "未执行",
                })

        return final_results

    def clear_cache(self) -> None:
        """清空结果缓存."""
        self._results_cache.clear()


# 全局并行执行器实例
_parallel_executor: ParallelExecutor | None = None


def get_parallel_executor(max_concurrency: int = 5) -> ParallelExecutor:
    """获取或创建并行执行器单例."""
    global _parallel_executor
    if _parallel_executor is None:
        _parallel_executor = ParallelExecutor(max_concurrency=max_concurrency)
    return _parallel_executor


def reset_parallel_executor() -> None:
    """重置并行执行器."""
    global _parallel_executor
    _parallel_executor = None

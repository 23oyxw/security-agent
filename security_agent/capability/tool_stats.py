"""工具使用统计 — MCP 评分维度硬性要求.

跟踪每个工具的:
    - 调用次数
    - 成功率
    - 平均延迟
    - 最近调用时间
    - 错误分布

持久化到 data/tool_stats.jsonl
API: capability/tool_stats.py::get_stats()

用法:
    from security_agent.capability.tool_stats import ToolStatsTracker

    tracker = ToolStatsTracker()
    tracker.record("get_system_health", ok=True, elapsed_ms=45.2)
    stats = tracker.get_stats()
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from typing import Any

from security_agent import config

_STATS_PATH = config.DATA_DIR / "tool_stats.jsonl"
_FLUSH_INTERVAL = 10  # 每 10 条批量刷盘


class ToolStatsTracker:
    """工具调用统计追踪器（线程安全）."""

    def __init__(self):
        self._lock = threading.Lock()
        self._buffer: list[dict[str, Any]] = []
        self._stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "calls": 0,
            "success": 0,
            "failure": 0,
            "total_latency_ms": 0.0,
            "last_called_at": 0.0,
            "last_error": "",
            "errors_by_type": defaultdict(int),
        })
        self._load()

    def record(self, tool_name: str, *, ok: bool, elapsed_ms: float = 0.0, error: str = "") -> None:
        """记录一次工具调用."""
        now = time.time()
        with self._lock:
            s = self._stats[tool_name]
            s["calls"] += 1
            if ok:
                s["success"] += 1
            else:
                s["failure"] += 1
            s["total_latency_ms"] += elapsed_ms
            s["last_called_at"] = now
            if error:
                s["last_error"] = error[:200]
                err_type = error.split(":")[0] if ":" in error else error[:30]
                s["errors_by_type"][err_type] += 1

            self._buffer.append({
                "tool": tool_name,
                "ok": ok,
                "elapsed_ms": elapsed_ms,
                "error": error[:200],
                "ts": now,
            })
            if len(self._buffer) >= _FLUSH_INTERVAL:
                self._flush()

    def get_stats(self) -> dict[str, Any]:
        """获取完整统计（MCP 评分维度需要展示的数据）."""
        with self._lock:
            tools = {}
            for name, s in sorted(self._stats.items()):
                calls = s["calls"]
                success = s["success"]
                failure = s["failure"]
                avg_latency = round(s["total_latency_ms"] / calls, 2) if calls > 0 else 0
                tools[name] = {
                    "calls": calls,
                    "success": success,
                    "failure": failure,
                    "success_rate": round(success / calls, 3) if calls > 0 else 1.0,
                    "avg_latency_ms": avg_latency,
                    "last_called_ago_sec": round(time.time() - s["last_called_at"], 0) if s["last_called_at"] else None,
                    "last_error": s["last_error"][:100],
                    "top_errors": dict(sorted(s["errors_by_type"].items(), key=lambda x: -x[1])[:3]),
                }

        return {
            "total_tools": len(tools),
            "total_calls": sum(s["calls"] for s in self._stats.values()),
            "overall_success_rate": self._overall_rate(),
            "tools": tools,
        }

    def get_tool_detail(self, tool_name: str) -> dict[str, Any]:
        """单个工具的详细统计."""
        stats = self.get_stats()
        return stats.get("tools", {}).get(tool_name, {"calls": 0, "note": "no data"})

    def get_summary(self) -> dict[str, Any]:
        """摘要（给 Dashboard/MCP 管理页）."""
        stats = self.get_stats()
        top_called = sorted(stats["tools"].items(), key=lambda x: -x[1]["calls"])[:5]
        lowest_success = sorted(stats["tools"].items(), key=lambda x: x[1]["success_rate"])[:3]
        return {
            "total_tools": stats["total_tools"],
            "total_calls": stats["total_calls"],
            "overall_success_rate": stats["overall_success_rate"],
            "top_5_by_calls": [{"name": n, **d} for n, d in top_called],
            "lowest_3_success_rate": [{"name": n, **d} for n, d in lowest_success],
        }

    def _overall_rate(self) -> float:
        total = sum(s["calls"] for s in self._stats.values())
        if total == 0:
            return 1.0
        ok = sum(s["success"] for s in self._stats.values())
        return round(ok / total, 3)

    def _flush(self) -> None:
        if not self._buffer:
            return
        try:
            _STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_STATS_PATH, "a", encoding="utf-8") as f:
                for entry in self._buffer:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._buffer.clear()
        except OSError:
            pass

    def _load(self) -> None:
        if not _STATS_PATH.exists():
            return
        try:
            for line in _STATS_PATH.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    self.record(
                        tool_name=entry.get("tool", "unknown"),
                        ok=entry.get("ok", False),
                        elapsed_ms=entry.get("elapsed_ms", 0),
                        error=entry.get("error", ""),
                    )
                except (json.JSONDecodeError, KeyError):
                    continue
        except OSError:
            pass


# 全局单例
_tracker: ToolStatsTracker | None = None


def get_tool_stats() -> ToolStatsTracker:
    global _tracker
    if _tracker is None:
        _tracker = ToolStatsTracker()
    return _tracker


# 快捷函数（供 tool_box 调用）
def record_tool_call(tool_name: str, ok: bool, elapsed_ms: float = 0.0, error: str = "") -> None:
    get_tool_stats().record(tool_name, ok=ok, elapsed_ms=elapsed_ms, error=error)

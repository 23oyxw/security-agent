"""记忆系统 + 任务优先级调度 Skill.

功能:
- 任务记忆: 记录运维历史任务、执行结果、失败原因
- 优先级调度: 基于紧急度/影响面/历史经验自动排优先级
- 智能回顾: 周期性回顾未完成/高频失败任务
- 上下文感知: 关联历史任务与当前告警，提供决策参考
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef


@dataclass
class TaskRecord:
    """任务记忆记录."""
    task_id: str
    title: str
    description: str
    priority: int  # 1=紧急 2=高 3=中 4=低
    status: str  # pending/running/done/failed/blocked
    created_at: float
    updated_at: float
    tags: list[str] = field(default_factory=list)
    result: str = ""
    fail_count: int = 0
    related_alert: str = ""
    context: dict[str, Any] = field(default_factory=dict)


class MemoryPrioritySkill(SkillBase):
    """记忆系统 + 任务优先级调度."""

    STORAGE_DIR = Path("data/memory")

    def __init__(self):
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._tasks_file = self.STORAGE_DIR / "task_memory.json"
        self._tasks: dict[str, TaskRecord] = {}
        self._load_tasks()

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="memory_priority",
            display_name="记忆系统 & 优先级调度",
            description="任务记忆、优先级智能排序、周期性回顾、历史关联决策",
            version="1.0.0",
            tags=("memory", "priority", "scheduling", "ai"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="memory_add_task",
                description="记录一个运维任务到记忆系统（支持自动优先级评估）",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "任务标题"},
                        "description": {"type": "string", "description": "任务描述"},
                        "priority": {"type": "integer", "description": "优先级 1-4（可选，不填自动评估）", "enum": [1, 2, 3, 4]},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "标签"},
                        "related_alert": {"type": "string", "description": "关联告警ID或描述"},
                    },
                    "required": ["title"],
                },
                handler=self.add_task,
            ),
            ToolDef(
                name="memory_list_tasks",
                description="列出记忆中的任务（支持按状态/优先级过滤）",
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "按状态过滤", "enum": ["pending", "running", "done", "failed", "blocked", "all"]},
                        "limit": {"type": "integer", "description": "返回数量", "default": 20},
                    },
                    "required": [],
                },
                handler=self.list_tasks,
            ),
            ToolDef(
                name="memory_update_task",
                description="更新任务状态（完成/失败/阻塞）",
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "任务ID"},
                        "status": {"type": "string", "description": "新状态", "enum": ["done", "failed", "blocked", "running"]},
                        "result": {"type": "string", "description": "执行结果描述"},
                    },
                    "required": ["task_id", "status"],
                },
                handler=self.update_task,
            ),
            ToolDef(
                name="memory_priority_queue",
                description="获取当前任务优先级队列（智能排序）",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.priority_queue,
            ),
            ToolDef(
                name="memory_review",
                description="周期性回顾：找出高频失败/长期未完成/关联告警的任务",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self.review,
            ),
            ToolDef(
                name="memory_context",
                description="根据当前告警/问题查询历史关联任务（决策参考）",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "当前告警或问题描述"},
                    },
                    "required": ["query"],
                },
                handler=self.context_lookup,
            ),
        ]

    # --- 核心方法 ---

    def _load_tasks(self):
        if self._tasks_file.exists():
            try:
                raw = json.loads(self._tasks_file.read_text("utf-8"))
                for k, v in raw.items():
                    self._tasks[k] = TaskRecord(**v)
            except Exception:
                self._tasks = {}

    def _save_tasks(self):
        data = {}
        for k, v in self._tasks.items():
            d = v.__dict__.copy()
            data[k] = d
        self._tasks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

    def _gen_id(self) -> str:
        import uuid
        return f"task-{uuid.uuid4().hex[:8]}"

    def _auto_priority(self, title: str, description: str, tags: list[str]) -> int:
        """根据关键词自动评估优先级."""
        text = f"{title} {description} {' '.join(tags)}".lower()
        if any(w in text for w in ["紧急", "critical", "崩溃", "宕机", "rootkit", "入侵", "数据泄露"]):
            return 1
        if any(w in text for w in ["高危", "漏洞", "僵尸", "异常", "告警", "入侵", "cpu 100"]):
            return 2
        if any(w in text for w in ["优化", "清理", "更新", "配置", "巡检"]):
            return 3
        return 4

    async def add_task(self, title: str, description: str = "", priority: int = 0,
                       tags: list[str] | None = None, related_alert: str = "") -> str:
        tags = tags or []
        if not priority:
            priority = self._auto_priority(title, description, tags)
        now = time.time()
        record = TaskRecord(
            task_id=self._gen_id(),
            title=title,
            description=description,
            priority=priority,
            status="pending",
            created_at=now,
            updated_at=now,
            tags=tags,
            related_alert=related_alert,
        )
        self._tasks[record.task_id] = record
        self._save_tasks()
        return json.dumps({
            "ok": True,
            "task_id": record.task_id,
            "priority": priority,
            "message": f"已记录任务「{title}」优先级={priority}",
        }, ensure_ascii=False)

    async def list_tasks(self, status: str = "all", limit: int = 20) -> str:
        tasks = list(self._tasks.values())
        if status != "all":
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: (t.priority, -t.updated_at))
        result = []
        for t in tasks[:limit]:
            result.append({
                "task_id": t.task_id,
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "tags": t.tags,
                "fail_count": t.fail_count,
                "updated_at": _fmt_time(t.updated_at),
            })
        return json.dumps({"total": len(result), "tasks": result}, ensure_ascii=False)

    async def update_task(self, task_id: str, status: str, result: str = "") -> str:
        task = self._tasks.get(task_id)
        if not task:
            return json.dumps({"ok": False, "error": f"任务 {task_id} 不存在"})
        task.status = status
        task.result = result
        task.updated_at = time.time()
        if status == "failed":
            task.fail_count += 1
        self._save_tasks()
        return json.dumps({"ok": True, "task_id": task_id, "new_status": status}, ensure_ascii=False)

    async def priority_queue(self) -> str:
        pending = [t for t in self._tasks.values() if t.status in ("pending", "blocked")]
        pending.sort(key=lambda t: (t.priority, t.fail_count * -1, -t.created_at))
        queue = []
        for i, t in enumerate(pending[:15], 1):
            queue.append({
                "rank": i,
                "task_id": t.task_id,
                "title": t.title,
                "priority": _priority_label(t.priority),
                "fail_count": t.fail_count,
                "waiting_since": _fmt_time(t.created_at),
            })
        return json.dumps({"queue_length": len(queue), "queue": queue}, ensure_ascii=False)

    async def review(self) -> str:
        now = time.time()
        findings = []
        # 高频失败
        for t in self._tasks.values():
            if t.fail_count >= 3:
                findings.append({
                    "type": "high_fail",
                    "task_id": t.task_id,
                    "title": t.title,
                    "fail_count": t.fail_count,
                    "recommendation": "建议人工排查根因或降级处理",
                })
        # 长期未完成 (>24h)
        for t in self._tasks.values():
            if t.status in ("pending", "blocked") and (now - t.created_at) > 86400:
                hours = int((now - t.created_at) / 3600)
                findings.append({
                    "type": "overdue",
                    "task_id": t.task_id,
                    "title": t.title,
                    "waiting_hours": hours,
                    "recommendation": "已等待超过24小时，建议重新评估优先级",
                })
        # 统计
        stats = {"pending": 0, "running": 0, "done": 0, "failed": 0, "blocked": 0}
        for t in self._tasks.values():
            if t.status in stats:
                stats[t.status] += 1
        return json.dumps({
            "findings_count": len(findings),
            "findings": findings,
            "stats": stats,
        }, ensure_ascii=False)

    async def context_lookup(self, query: str) -> str:
        """根据关键词匹配历史任务."""
        query_lower = query.lower()
        matches = []
        for t in self._tasks.values():
            text = f"{t.title} {t.description} {' '.join(t.tags)} {t.related_alert}".lower()
            # 简单关键词匹配
            score = sum(1 for word in query_lower.split() if word in text)
            if score > 0:
                matches.append((score, t))
        matches.sort(key=lambda x: -x[0])
        results = []
        for score, t in matches[:5]:
            results.append({
                "task_id": t.task_id,
                "title": t.title,
                "status": t.status,
                "result": t.result[:200] if t.result else "",
                "match_score": score,
            })
        return json.dumps({"query": query, "matches": len(results), "tasks": results}, ensure_ascii=False)

    def get_rules(self) -> list[str]:
        return [
            "任务记忆: 每次运维操作都应记录到记忆系统，形成运维知识积累",
            "优先级排序: 紧急(崩溃/入侵) > 高危(漏洞/告警) > 中(优化/巡检) > 低(文档/美化)",
            "周期回顾: 每日回顾失败任务和长期未完成任务，避免遗漏",
            "关联决策: 处理告警前先查历史记忆，避免重复排查",
        ]


def _priority_label(p: int) -> str:
    return {1: "🔴 紧急", 2: "🟠 高", 3: "🟡 中", 4: "🟢 低"}.get(p, "未知")


def _fmt_time(ts: float) -> str:
    if not ts:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
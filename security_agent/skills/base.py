"""Skill 基类 — 定义 Skill 的标准接口."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

# 复用已有类型
from security_agent.knowledge.playbooks import Playbook


@dataclass
class ToolDef:
    """Skill 提供的工具定义."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[str] | str]
    auto_ok: bool = True  # 是否允许自动执行（不需确认）


@dataclass
class SkillMeta:
    """Skill 元信息."""

    name: str
    display_name: str
    description: str
    version: str = "1.0.0"
    author: str = "security-agent"
    tags: tuple[str, ...] = ()
    requires_root: bool = False


class SkillBase(ABC):
    """所有 Skill 的基类.

    子类需实现:
      - meta: SkillMeta 属性
      - get_tools(): 返回本 Skill 提供的工具列表
      - healthcheck(): Skill 自检
    """

    @property
    @abstractmethod
    def meta(self) -> SkillMeta:
        """返回 Skill 元信息."""
        ...

    @abstractmethod
    def get_tools(self) -> list[ToolDef]:
        """返回本 Skill 注册的工具列表."""
        ...

    def get_playbooks(self) -> list[Playbook]:
        """返回本 Skill 关联的知识库条目（可选）."""
        return []

    def get_rules(self) -> list[str]:
        """返回本 Skill 的运维规则（注入 LLM system prompt）."""
        return []

    async def healthcheck(self) -> dict[str, Any]:
        """Skill 自检，返回健康状态."""
        return {"ok": True, "skill": self.meta.name, "message": "未实现自检"}

    async def on_alert(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """告警事件回调 — 升级策略引擎调用（可选）.

        返回 None 表示本 Skill 不处理该事件。
        返回 dict 表示处置建议或自动修复结果。
        """
        return None

    def summary(self) -> str:
        """返回 Skill 摘要（供 UI 展示）."""
        m = self.meta
        tools = self.get_tools()
        return (
            f"[{m.name}] {m.display_name} v{m.version}\n"
            f"  {m.description}\n"
            f"  工具: {len(tools)} 个\n"
            f"  标签: {', '.join(m.tags) or '无'}"
        )
"""Skill 注册中心 — 发现、注册、路由 Skill."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from security_agent.skills.base import SkillBase, ToolDef
from security_agent.knowledge.playbooks import Playbook

# 全局 Skill 注册表
_skills: dict[str, SkillBase] = {}


def register(skill: SkillBase) -> None:
    """注册一个 Skill 实例."""
    _skills[skill.meta.name] = skill


def get_skill(name: str) -> SkillBase | None:
    return _skills.get(name)


def list_skills() -> list[dict[str, Any]]:
    """列出所有已注册 Skill 的摘要."""
    return [
        {
            "name": s.meta.name,
            "display_name": s.meta.display_name,
            "description": s.meta.description,
            "version": s.meta.version,
            "tags": list(s.meta.tags),
            "tool_count": len(s.get_tools()),
            "requires_root": s.meta.requires_root,
        }
        for s in _skills.values()
    ]


def collect_tools() -> list[ToolDef]:
    """收集所有 Skill 提供的工具."""
    tools: list[ToolDef] = []
    for skill in _skills.values():
        tools.extend(skill.get_tools())
    return tools


def collect_playbooks() -> list[Playbook]:
    """收集所有 Skill 关联的知识库条目."""
    pbs: list[Playbook] = []
    for skill in _skills.values():
        pbs.extend(skill.get_playbooks())
    return pbs


def collect_rules() -> list[str]:
    """收集所有 Skill 的运维规则."""
    rules: list[str] = []
    for skill in _skills.values():
        rules.extend(skill.get_rules())
    return rules


def collect_tool_schemas_openai() -> list[dict[str, Any]]:
    """将所有 Skill 工具转为 OpenAI function calling 格式."""
    schemas: list[dict[str, Any]] = []
    for tool in collect_tools():
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
        )
    return schemas


def merge_skill_tools_into_registry() -> None:
    """将 Skill 工具合并到 tools/registry.py 的 TOOL_REGISTRY（兼容层）."""
    from security_agent.tools.registry import TOOL_REGISTRY

    for tool in collect_tools():
        if tool.name not in TOOL_REGISTRY:
            TOOL_REGISTRY[tool.name] = (
                tool.description,
                tool.parameters,
                tool.handler,
            )


async def route_alert_to_skills(event: dict[str, Any]) -> list[dict[str, Any]]:
    """将告警事件路由到所有 Skill 的 on_alert 回调."""
    results: list[dict[str, Any]] = []
    for skill in _skills.values():
        try:
            result = await skill.on_alert(event)
            if result is not None:
                result["skill"] = skill.meta.name
                results.append(result)
        except Exception as exc:  # noqa: BLE001
            results.append({
                "skill": skill.meta.name,
                "error": str(exc),
            })
    return results


def auto_discover() -> None:
    """自动发现并注册 skills 包下所有子模块中的 Skill 实例.

    支持两种结构:
      1. security_agent/skills/xxx.py（单文件 Skill）
      2. security_agent/skills/xxx/skill.py（目录包 Skill）
    """
    import security_agent.skills as skills_pkg

    skip = {"base", "registry", "__init__"}
    for _importer, modname, ispkg in pkgutil.iter_modules(skills_pkg.__path__):
        if modname in skip or modname.startswith("_"):
            continue
        try:
            if ispkg:
                # 目录包: security_agent/skills/xxx/skill.py
                mod = importlib.import_module(f"security_agent.skills.{modname}.skill")
            else:
                # 单文件: security_agent/skills/xxx.py
                mod = importlib.import_module(f"security_agent.skills.{modname}")

            # 约定：每个 Skill 模块导出 skill_instance 或 SKILL_CLASS
            if hasattr(mod, "skill_instance"):
                register(mod.skill_instance)
            elif hasattr(mod, "SKILL_CLASS"):
                register(mod.SKILL_CLASS())
        except Exception:  # noqa: BLE001
            pass  # 静默跳过加载失败的 Skill

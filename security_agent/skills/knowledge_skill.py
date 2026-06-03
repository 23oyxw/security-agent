"""知识库 Skill — 封装安全知识检索与建议生成能力."""

from __future__ import annotations

import json
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef


class KnowledgeSkill(SkillBase):
    """安全知识库检索、索引构建与基于上下文的建议生成."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="knowledge",
            display_name="安全知识库",
            description="检索安全知识库、构建向量索引、生成基于扫描结果的结构化建议",
            version="1.0.0",
            tags=("knowledge", "retrieval", "advice"),
        )

    def get_rules(self) -> list[str]:
        return ["重要操作前先检索知识库 grounding，减少幻觉风险"]

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="search_security_knowledge",
                description="检索安全知识库（防幻觉 grounding），返回 PB 编号与建议/禁止事项",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "用户问题或现象描述"},
                        "top_k": {"type": "integer", "default": 5},
                        "threat_tag": {
                            "type": "string",
                            "description": "可选过滤: misdelete|exfiltration|port_exposure|privilege|...",
                            "default": "",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.search,
            ),
            ToolDef(
                name="build_knowledge_index",
                description="构建/更新知识库向量索引（需 LLM Embedding API）",
                parameters={
                    "type": "object",
                    "properties": {"force": {"type": "boolean", "default": False}},
                    "required": [],
                },
                handler=self.build_index,
            ),
            ToolDef(
                name="get_grounded_advice",
                description="结合当前扫描与知识库生成结构化建议（结论/步骤/请勿/是否需确认）",
                parameters={
                    "type": "object",
                    "properties": {"user_message": {"type": "string"}},
                    "required": ["user_message"],
                },
                handler=self.grounded_advice,
            ),
        ]

    async def search(self, query: str, top_k: int = 5, threat_tag: str = "") -> str:
        from security_agent.retrieval.hybrid import search_knowledge

        tag = threat_tag or None
        hits = search_knowledge(query, top_k=top_k, threat_tag=tag)
        return json.dumps({"query": query, "hits": hits}, ensure_ascii=False, indent=2)

    async def build_index(self, force: bool = False) -> str:
        from security_agent.retrieval.hybrid import build_vector_index

        return json.dumps(build_vector_index(force=force), ensure_ascii=False, indent=2)

    async def grounded_advice(self, user_message: str) -> str:
        from security_agent.agent.advisor import build_structured_advice, format_advice_for_user
        from security_agent.scanner.engine import run_security_scan

        scan = run_security_scan()
        advice = build_structured_advice(
            user_message,
            risks=scan.get("risks", []),
            tool_summary=json.dumps(scan, ensure_ascii=False)[:2000],
        )
        advice["formatted"] = format_advice_for_user(advice)
        return json.dumps(advice, ensure_ascii=False, indent=2)


# Skill 自动发现入口
skill_instance = KnowledgeSkill()

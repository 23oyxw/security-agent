---
tier: T4
source: docs\architecture\ARCHITECTURE_TIER_MAP.md
---

# 架构分级对照图（建议 vs 实现 vs 开源）

> 权威索引：`FINAL_ARCHITECTURE.md` · `ENCAPSULATION_TO_L5_ROADMAP.md` · 本文 T0-T4 分级

## 分级总览

| 级别 | 名称 | 仓库落点 | Gitee Wiki 导出 |
|------|------|----------|-----------------|
| T0 | 定义封装 | `data/mcp/workflow_manifest.json` · `skills/` | `data/wiki_export/T0-definition.md` |
| T1 | 五层流水线 | `api/agent_plan.py` · `core_agents.py` | `T1-pipeline.md` |
| T2 | 数学量化 | `l5/analytics.py` · `cluster_analytics.py` | `T2-math.md` |
| T3 | 工作流标注 | `pipeline/htn_planner.py` · `/api/workflow/manifest` | `T3-workflow.md` |
| T4 | 沙箱全包 | `pipeline/sandbox_gate.py` · `terminal/sandbox.py` | `T4-sandbox.md` |

## 《些许真实建议》对照

| 建议主题 | 实现状态 | 本仓库 | 可借鉴 OSS |
|----------|----------|--------|------------|
| HTN 0-1 工具路径 | 已落地 | `htn_planner.py` | LangGraph |
| MCP 工作流封装 | 已落地 | `workflow_manifest.json` | MCP SDK |
| 五层刚性流水线 | 已落地 | `agent_plan.py` | pytest integration |
| L1 DBSCAN 边界 | 已落地 | `cluster_analytics.py` | 自研无 sklearn |
| L5 3sigma/IQR/热力 | 已落地 | `analytics.py` | statistics |
| 知识 3 要点+来源 | 已落地 | `knowledge_contract.py` | — |
| 沙箱全包写操作 | 已加强 | `sandbox_gate` + `force_sandbox` | — |
| RAG 六环节 | 部分 | `hybrid.py` | Ragas |
| 外部攻击集成测试 | 已落地 | `external_sim.py` · L5 外部 Tab | — |
| 告警风暴降噪 | 已落地 | `alert_aggregator.py` | — |
| 环境修复专页 | 已落地 | `/repair` · `repair_routes.py` | — |
| L5 策略反写 L1 | 已落地 | `policy_feedback.py` | `l1_tuning.json` |
| Wiki 回流 | 部分 | `sync_gitee_wiki.sh` + `build_wiki_tier_bundle.py` | Gitee API |

## 文档阅读顺序（答辩）

1. `ARCHITECTURE_TIER_MAP.md`（本文）
2. `ENCAPSULATION_TO_L5_ROADMAP.md`
3. `FIVE_LAYER_PIPELINE.md`
4. `L5_ANALYTICS.md`
5. `FINAL_ARCHITECTURE.md`（终版权威）

## API 分级索引

| 级别 | 端点 |
|------|------|
| T1 | `POST /api/agent/plan` |
| T2 | `GET /api/l5/math-catalog` · `/clusters` · `/scatter` |
| T3 | `GET /api/workflow/manifest` · `/tier-catalog` |
| T4 | `POST /api/executor/execute`（经 sandbox_gate） |
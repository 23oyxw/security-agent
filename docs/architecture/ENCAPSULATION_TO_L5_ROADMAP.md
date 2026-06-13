# 定义封装 → 五层流水线 → 数学模型（落地路线图）

> 对齐《些许真实建议》与 FINAL_ARCHITECTURE.md · 更新 2026-06-13

## 1. 三层总览

| 层次 | 本仓库落点 | 开源参考 |
|------|-----------|----------|
| 定义封装 | data/mcp/workflow_manifest.json · skills/ | LangGraph · dive-into-llms |
| 五层流水线 | api/agent_plan.py · core_agents.py | pytest integration |
| 数学模型 | l5/analytics.py · cluster_analytics.py | statistics · 自研 DBSCAN |

## 2. 定义封装

- tool_taxonomy.py：四工具簇 metrics/logs/repair/dispatch
- workflow_manifest.json：意图 → 工具链 → HTN 步骤
- skills/flows：L2 Skill Flow 封装

## 3. HTN 0-1 路径

htn_planner.py：去重 → 按簇排序 → 最小 0-1 代价 → 匹配 manifest

接入：agent_plan.py 产出 plan.htn_path

## 4. 五层流水线

L1 analyze → L2 safety → GATE → L3 execute → L4 audit → L5 analytics

## 5. 数学模型

| 模型 | 层 | 文件 |
|------|-----|------|
| DBSCAN-2D 边界 | L1 | cluster_analytics.py |
| HTN 0-1 | L3 | htn_planner.py |
| 3σ + IQR | L5 | analytics.py |
| weighted_density | L5 | analytics.py |
| 3-bullet + source | L1 | knowledge_contract.py |

## 6. API

- POST /api/agent/plan — htn_path, triple_perception
- GET /api/l5/math-catalog
- GET /api/l5/clusters
- GET /api/l5/scatter

## 7. 龙芯部署

git pull gitee master
bash scripts/bootstrap-kylin-loongarch-pip.sh
bash scripts/boot_start_loongarch.sh

## 8. 验证

PYTHONPATH=. py -3.10 -c "from security_agent.pipeline.htn_planner import optimize_tool_chain; print(optimize_tool_chain(['list_processes','get_system_health'],'health'))"
curl http://127.0.0.1:8900/api/health
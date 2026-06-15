# 三方统一契约

> **唯一真源**：[`data/contracts/triple_unify.json`](../data/contracts/triple_unify.json)

前端、后端、文档共用同一份 JSON，避免 Agent 描述、主线层级（含 GATE）、流水线 stage、画布节点映射各自漂移。

## 消费方

| 方 | 路径 | 方式 |
|----|------|------|
| 后端 | `security_agent/contracts/loader.py` | `get_contract()` |
| 后端 | `security_agent/agent/agent_registry.py` | 启动时从契约派生 |
| API | `GET /api/agent/contract` | 完整契约 JSON |
| API | `GET /api/agent/registry` | 精简注册表（含 `pipeline_layer_detail`） |
| 前端 | `frontend/src/constants/from-contract.js` | Vite 直接 import JSON |
| 画布 | `frontend/src/constants/canvas-spine-map.js` | `stage_spine_map` + L3 簇轨动态展开 |
| 校验 | `scripts/verify_triple_unify.py` | 提交前跑一遍 |

## 主线公式

**1调度 + 1安全 + 1迭代** → `L1 → L2 → GATE → L3 → L4 → L5`

## 校验

```bash
python scripts/verify_triple_unify.py
```

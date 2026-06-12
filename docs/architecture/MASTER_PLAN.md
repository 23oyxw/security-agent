# 银河麒麟智能安全运维 Agent — 总控计划

> **定位**：A2 赛题唯一权威路线图，统领三条交付线、**五层智能体流水线**与分阶段验收。  
> **更新**：2026-06-11  
> **Agent 编排权威**：[FIVE_LAYER_PIPELINE.md](FIVE_LAYER_PIPELINE.md)  
> **关联**：[TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) · [TECH_STACK.md](TECH_STACK.md) · [../OPTIMIZATION_PLAN.md](../OPTIMIZATION_PLAN.md)

---

## 图例

| 符号 | 含义 |
|------|------|
| ✅ | 已完成，可演示 |
| ⚠️ | 部分完成 / 待联调验证 |
| ❌ | 未开始 |
| 📦 | 仅在 qt01 参考库，不并入主干 |
| 🔴 | 答辩风险 / 需决策 |

---

## 0. 五层智能体流水线（重构主线）

> **完整规格**：[FIVE_LAYER_PIPELINE.md](FIVE_LAYER_PIPELINE.md)

### 0.1 核心约束

- 智能体主界面：**计划模式 / 执行模式** 双切换
- **先分析后执行**：批量指令亦须先 L1 分析计划
- **L1/L2 不决策**：有工具接口也不得立即执行写操作
- **L1 与 L3 共用 Agent**（`mode=plan|execute`）
- **MCP 工具 + 封装流程** 同一模块；工具分 metrics/logs/repair/schedule，单一职责
- **知识数据**（边界对抗、规范库、回流案例）→ **Gitee Wiki**

### 0.2 五层一览

| 层 | 名称 | 关键能力 | 当前状态 |
|----|------|----------|----------|
| L1 | 感知与计划 | 分析计划 · 边界感知 · 知识检索 · 静态感知 · 意图识别 | ⚠️ |
| L2 | 安全管控 | 护栏/熔断/确认/CPU弹窗 ∥ 沙箱试跑 | ✅ 部分 |
| L3 | 推理分发执行 | MCP+Flow · 四类工具 | ⚠️ |
| L4 | 审计与回流 | trace · 卷宗 · Wiki 回流 | ✅ 审计 / ❌ 回流 |
| L5 | 数学模型 | Agent 指标 · 感知/链路绘图 | ❌ |

### 0.3 与赛题五大支柱

支柱是**能力域**，五层是**运行时阶段**——见 [FIVE_LAYER_PIPELINE.md §6](FIVE_LAYER_PIPELINE.md#6-与-a2-五大支柱对照)。

---

## 1. 三交付线战略

本项目采用 **三条可独立演进、经 API 解耦** 的交付线，避免 qt01 整包复制与双前端逻辑分叉。

```text
                    ┌─────────────────────────────────────┐
                    │  C. qt01（参考库，不部署、不 import）   │
                    │  Qt 流程图 / Dify / 完整 pytest 套件   │
                    └──────────────────┬──────────────────┘
                                       │ 择优迁入 A（已迁：三层防御、mac_checker）
┌──────────────┐   REST/WS    ┌───────▼────────────────────────┐
│ B1 Streamlit │─────────────►│  A. security_agent + FastAPI    │
│  :8501       │  可直连 Python│  :8000（API + dist 静态托管）    │
├──────────────┤              │  五大支柱 · Agent · SafetyGate   │
│ B2 Vue3 SPA  │── Axios ───►│                                  │
│  :5173 dev   │              └───────────────┬──────────────────┘
└──────────────┘                              ▼
                                    OS / 麒麟 / data/
```

### 1.1 A 线 — 核心后端（主交付）

| 项 | 状态 | 说明 |
|----|------|------|
| FastAPI 五大支柱路由 | ✅ | `/api/perception` `mcp` `safety` `executor` `trace` + 扩展路由 |
| AgentBrain + Orchestrator | ✅ | 意图识别、工具链、三层防御执行入口 |
| 三层防御 30/35/35 | ✅ | 自 qt01 迁入，`tests/test_three_layer_defense.py` 全过 |
| 5 MCP Skill 包 + 6 单文件 Skill | ✅ | stdio MCP + registry 自动发现 |
| 沙箱 + PrivilegeBroker | ✅ | `terminal/sandbox.py` + `privilege.py` |
| L2 Skill Flow | ✅ | `skills/flows/runner.py` 6 flow；REST `/api/skills/flows` 已暴露 |
| MCP 热插拔 | ✅ | `mcp/registry.py` + `POST /api/mcp/reload` |
| mac_checker 执行链 | ✅ | `terminal/executor.py` 执行前 MAC 钩子 + 审计 |

**原则**：新能力先进 A；B 只调 `/api/*`；C 只读参考。

### 1.2 B1 线 — Streamlit 控制台（开发 / 功能最全）

| 项 | 状态 | 说明 |
|----|------|------|
| 九页 + 风险演练 + 自主运维 | ✅ | `streamlit_app.py` + `ui/pages*.py` |
| 三维态势可视化 | ✅ | Plotly 3D / 雷达 / 时间线 |
| Skill 插件页 | ✅ | 5 大 Skill 详情展示 |
| 答辩主路径 | ⚠️ | 可用，但 B/S 答辩更推荐 B2 + A 静态托管 |

### 1.3 B2 线 — Vue3 SPA（B/S 答辩目标）

| 项 | 状态 | 说明 |
|----|------|------|
| 10 页面 + 路由 + Pinia | ✅ | Element Plus + Axios 封装 |
| `npm run build` → `frontend/dist` | ✅ | dist 已存在（2026-05-29） |
| FastAPI 静态托管 | ✅ | `app.py` mount `/assets` + SPA fallback |
| API 字段对齐 | ⚠️ | 代码已对接；`scripts/e2e_api_smoke.py` 可自动验 |
| Pinia 多 store 拆分 | ✅ | `user` `alerts` `metrics` `mcp` |

### 1.4 C 线 — qt01 参考库

| 能力 | 主干状态 | qt01 位置 | 决策 |
|------|----------|-----------|------|
| 三层防御 | ✅ 已迁入 | `safety_gate/three_layer_defense.py` | — |
| mac_checker | ⚠️ 已迁入未强制 | `safety_gate/mac_checker.py` | P1 接入 executor |
| MCP 热插拔 | ✅ | `mcp/registry.py` | 已完成 |
| Qt 流程图编辑器 | ❌ | `qt-security-flow/` | P2 答辩备选，不并入 |
| Dify 工作流 | ❌ | `dify_integration/` | 可选，不阻塞 P0 |
| AIFlowy 平台 | 📦 | `aiflowy-main/` | 只读参考，见 [AIFLOWY_UTILIZATION.md](AIFLOWY_UTILIZATION.md) |
| 多 Agent | ❌ | `agent/multi_agent.py` | P2 可选 |
| reasoning_engine | ❌ | `agent/reasoning_engine.py` | 按需评估 |

---

## 2. 解耦与 Skill 封装分层（L1 / L2 / L3）

### 2.1 分层定义

```text
┌─────────────────────────────────────────────────────────────┐
│ L3 编排胶水（主干 agent/）                                    │
│  orchestrator · brain · autonomous · workflow/engine        │
│  职责：意图识别、LLM 工具选择、trace 贯穿、调用 L2 flow       │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│ L2 Skill Flow（skills/flows/）— 多步确定性流程                  │
│  secure_exec · alert_response · scan_report · …              │
│  职责：固定步骤链、可测试、可答辩演示，不含 LLM 自由推理         │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│ L1 原子能力                                                    │
│  tools/registry · skills/*/skill.py · terminal · scanner     │
│  职责：单工具/单 MCP 调用、最小副作用、可并行                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 什么放 Skill，什么放主干

| 放 L1 Skill / MCP | 放 L2 Flow | 放 L3 主干 |
|-------------------|------------|------------|
| 单一运维动作（查日志、查进程） | 固定多步剧本（扫描→报告） | LLM 对话与意图路由 |
| MCP stdio 独立进程工具 | 告警→Skill 路由→汇总 | 自主任务状态机 |
| Playbook / 规则片段 | 安全执行（评估→确认→执行） | 成本、回退、升级策略 |
| `on_alert` 回调 | 可复现的演示流程 | JWT、CORS、静态托管 |

### 2.3 解耦强制规则

1. **UI 不 import 业务** — Vue / Streamlit 只调 `/api/*`
2. **写操作必经 SafetyGate** — 或 `run_with_three_layer_defense` / L2 `secure_exec`
3. **trace_id 贯穿** — `audit/trace.py` + `reasoning_trace.py`
4. **qt01 隔离** — 不参与 `uv run` 默认路径、不 CI
5. **配置单入口** — `security_agent/config.py`

### 2.4 当前 Skill 资产清单

| 类型 | 路径 | 数量 | 状态 |
|------|------|------|------|
| MCP Skill 包 | `skills/{healthcheck,log_analyzer,...}/` | 5 | ✅ |
| 单文件 Skill | `skills/*_skill.py` | 6 | ✅ |
| MCP Launcher | `skills/launcher.py` | — | ✅ |
| L2 Flow | `skills/flows/runner.py` | 6 | ✅ 含 cleanup/stress |
| L3 胶水 | `agent/orchestrator.run_with_three_layer_defense` | — | ✅ |

---

## 3. 分阶段路线图

### Phase 0 — 基线与文档

| 任务 | 状态 | 备注 |
|------|------|------|
| 项目结构 + pyproject / uv | ✅ | |
| TECHNICAL_ARCHITECTURE.md v0.7 | ✅ | |
| **MASTER_PLAN.md（本文）** | ✅ | 2026-05-30 |
| GAP_ANALYSIS 历史对照 | ✅ | 已加过时标记，沙箱等已实现 |
| A2 得分点映射文档 | ✅ | `docs/A2_ARCHITECTURE_MAPPING.md` |
| CI / pre-commit | ❌ | 可选 |
| 统一版本号（API 0.6 vs 文档 0.7） | ✅ | 已对齐 0.7.0 |

### Phase 1 P0 — Vue 联调 + 三层防御演示

**目标**：B/S 单端口答辩路径跑通；安全闸门可演示。

| # | 任务 | 状态 |
|---|------|------|
| 1 | 三层防御迁入 + 单测 | ✅ |
| 2 | `orchestrator.run_with_three_layer_defense` | ✅ |
| 3 | Vue SafetyGate → `POST /api/safety/defense/evaluate` | ✅ 代码已对齐 |
| 4 | Vue Executor → `POST /api/executor/execute` | ✅ 代码已对齐 |
| 5 | Vue Trace / MCP / Alerts / Knowledge / Users | ✅ 代码已对齐 |
| 6 | `npm run build` + dist 存在 | ✅ |
| 7 | FastAPI SPA 静态托管 | ✅ |
| 8 | **端到端联调验收**（登录→仪表盘→安全闸门→执行器） | ⚠️ **待人工** → [P0_FRONTEND_WALKTHROUGH.md](../P0_FRONTEND_WALKTHROUGH.md) |
| 9 | Dashboard / AgentChat / Login API 字段验证 | ⚠️ AgentChat 已展示 trace/降级；其余待人工 |
| 10 | 答辩演示脚本（3 分钟三层防御） | ✅ `scripts/demo_three_layer_defense.sh` |

**P0 验收清单**：

```bash
# 1. 三层防御单测
.venv/bin/python tests/test_three_layer_defense.py

# 2. 启动 API（含 dist）
uv run uvicorn security_agent.api.app:app --host 0.0.0.0 --port 8000

# 3. 健康检查
curl -s http://127.0.0.1:8000/api/health | jq .

# 4. 安全评估 API
curl -s -X POST http://127.0.0.1:8900/api/safety/defense/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"target":"rm -rf /","target_type":"terminal","user_message":"删除临时文件"}' | jq .

# 5. 浏览器：http://127.0.0.1:8000/ → 登录 admin/admin123 → 安全闸门页测试

# 6. Vue 开发模式（可选）
cd frontend && npm run dev   # :5173 → proxy :8000
```

### Phase 2 P1 — MCP 热插拔、主动感知、mac_checker

| # | 任务 | 状态 | 优先级 |
|---|------|------|--------|
| 1 | 从 qt01 迁入 `mcp/plugin_manager.py` | ✅ | 已迁入 plugins/ |
| 2 | `mac_checker` 接入 executor 执行前钩子 | ⚠️ | 高（麒麟得分点） |
| 3 | `agent/perception.py` 主动上下文采集 | ⚠️ | 中 |
| 4 | L2 flow 暴露 REST `/api/skills/flows/run` | ✅ | 已实现 |
| 5 | Vue Dashboard / AgentChat 字段与 `models.py` 对齐 | ⚠️ | 中 |
| 6 | Pinia stores 拆分（alerts / agent / safety） | ❌ | 低 |
| 7 | `run_skill_flow` 接入 orchestrator 意图 `autonomous` | ❌ | 中 |

### Phase 3 P2 — 只读流程图、多 Agent（可选）

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 1 | Vue 只读流程图页 | ✅ `/workflow` + `configs/workflows/autonomous_ops.json` |
| 2 | qt01 multi_agent 择优评估 | 📦 | 性价比低可跳过 |
| 3 | WebSocket Agent 流式 | ✅ | `/api/agent/ws/chat` |
| 4 | Dify 集成 | ✅ | `/api/dify/*` + `security_agent/dify/bridge.py` |

### Phase 4 — 答辩材料

| # | 交付物 | 状态 |
|---|--------|------|
| 1 | 演示环境一键启动脚本说明 | ⚠️ `boot_start.sh` 仅 Streamlit |
| 2 | 三层防御 + 最小权限 + trace 演示路径 | ⚠️ |
| 3 | MCP Skill 列表截图 / 录屏 | ❌ |
| 4 | 架构图（三交付线 + L1/L2/L3） | ✅ 本文 + TECHNICAL |
| 5 | 赛题得分点对照表 | ✅ A2_ARCHITECTURE_MAPPING |
| 6 | 风险与应答话术 | ⚠️ 见 §8 |

---

## 4. Vue 前端页面完成度矩阵

| 路由 | 页面 | 主要 API | 路由 | 页面 UI | API 对接 | 联调验证 |
|------|------|----------|------|---------|----------|----------|
| `/login` | Login.vue | `POST /api/auth/login` | ✅ | ✅ | ⚠️ | ⚠️ 待验 |
| `/` | Dashboard.vue | perception, alerts, mcp, health | ✅ | ✅ | ⚠️ | ⚠️ 待验 |
| `/agent` | AgentChat.vue | `POST /api/agent/chat`, mcp | ✅ | ✅ | ⚠️ | ⚠️ 待验 |
| `/safety` | SafetyGate.vue | `POST /api/safety/defense/evaluate` | ✅ | ✅ | ✅ | ⚠️ 待验 |
| `/executor` | Executor.vue | `POST /api/executor/execute` | ✅ | ✅ | ✅ | ⚠️ 待验 |
| `/trace` | TraceView.vue | `GET /api/trace/` `/{id}/export` | ✅ | ✅ | ✅ | ⚠️ 待验 |
| `/mcp` | MCPManage.vue | `GET /api/mcp/servers` | ✅ | ✅ | ✅ | ⚠️ 待验 |
| `/alerts` | Alerts.vue | `GET/POST /api/alerts/` | ✅ | ✅ | ✅ | ⚠️ 待验 |
| `/knowledge` | Knowledge.vue | playbooks, search | ✅ | ✅ | ✅ | ⚠️ 待验 |
| `/users` | Users.vue | `GET/POST/DELETE /api/auth/users` | ✅ | ✅ | ✅ | ⚠️ 待验 |

**汇总**：路由 10/10 ✅ · UI 骨架 10/10 ✅ · API 代码对接 8/10 ✅、2/10 ⚠️ · **端到端联调 0/10 正式签字**（均需 P0 人工验收）

**缺口页面**（赛题非必须）：报告中心、监控详情、成本、自主运维、Skill Flow 控制台。

---

## 5. 后端模块完成度矩阵（五大支柱）

| 支柱 | 核心模块 | API | 单测 | 状态 |
|------|----------|-----|------|------|
| ① OS 深度感知 | `scanner/` `monitor/` `agent/perception.py` | `/api/perception/context` 等 | ⚠️ 部分 | ⚠️ 主动快照已加 |
| ② MCP 插件化 | `tools/` `skills/` `mcp/registry.py` | `/api/mcp` | ✅ | ✅ 热插拔 reload |
| ③ 安全意图校验 | `safety_gate/` `rules/` | `/api/safety` | ✅ | ✅ 含三层防御 |
| ④ 最小权限执行 | `terminal/privilege.py` `sandbox.py` `executor.py` | `/api/executor` | ⚠️ | ✅ 沙箱已有；⚠️ mac_checker |
| ⑤ 推理链路溯源 | `audit/spine.py` 事件脊柱 | `/api/trace` `/export` | ✅ | ✅ 统一 trace_id |
| 弹性 | `resilience/` 预算·熔断·降级 | `/api/resilience/status` | ✅ | ✅ |

### 5.0 事件脊柱与弹性（Incident Spine）— 2026-05-30 落地

**目标**：审计追踪、兜底策略、超时熔断三条能力合成一条可答辩的「事件脊柱」。

```text
trace_id（脊柱）
  ├─ audit.log（append-only 合规证据）
  ├─ TraceStorage 六阶段（receive → post_verify）
  ├─ ReasoningTrace jsonl（思考/工具/安全校验细粒度）
  └─ degradation_level（S0 全能力 → S2 规则/Playbook）
```

| 能力 | 模块 | API / 行为 |
|------|------|------------|
| 脊柱统一 | `audit/spine.py` `incident_spine()` | Brain / WS 共用 `trace_id` |
| 请求预算 | `resilience/budget.py` | `REQUEST_BUDGET_SEC` 子切片 llm/tools/… |
| 依赖熔断 | `resilience/circuit.py` | `llm:*` `dify:proxy` 连续失败打开 |
| 降级阶梯 | `resilience/degradation.py` | 模型全挂 → L2 Skill Flow / Playbook（S2） |
| 执行后验证 | `spine.post_verify()` | `secure_exec` flow 与工具调用后记录 |
| 卷宗导出 | `export_incident_bundle()` | `GET /api/trace/{id}/export` |
| S4 审批队列 | `confirm/confirmation.py` SQLite | 评估入队 · 超时 `timeout` · 执行需 `approval_id` |
| 执行前守卫 | `ops/guardrails.py` | executor 三层防御 + 工具 MCP 熔断 + 预算 |
| 就绪探针 | `GET /api/health/ready` | confirmations / trace / 熔断状态 |

| 级别 | 含义 | 触发 |
|------|------|------|
| S0 | LLM + 工具 + RAG | 默认 |
| S1 | 备用模型 | `FallbackClient` |
| S2 | 规则 / L2 flow / Playbook | 主备模型均失败 |
| S3 | 只读诊断 | SafetyGate deny（已有） |
| S4 | 人工审批 | `ConfirmationManager` SQLite + 超时 + `approval_id` 执行 ✅ |

### 5.1 安全控制层明细

| 模块 | 状态 |
|------|------|
| `gate.py` SafetyGate | ✅ |
| `risk.py` 四级风险 | ✅ |
| `intent.py` 意图审计 | ✅ |
| `injection_defense.py` | ✅ |
| `three_layer_defense.py` | ✅ |
| `mac_checker.py` | ✅ executor 前钩子 |
| `orchestrator.run_with_three_layer_defense` | ✅ |

### 5.2 Agent 与编排

| 模块 | 状态 |
|------|------|
| `brain.py` | ✅ `incident_spine` + S2 降级 + ReAct 上下文治理（§5.3） |
| `agent/react_context.py` | ✅ 工具观测截断 / 首轮瘦身 / 每轮预算 |
| `agent/fallback.py` | ✅ 熔断 + 预算超时 |
| `resilience/*` | ✅ 预算 / 熔断 / 降级 |
| `orchestrator.py` | ✅ |
| `autonomous.py` | ✅ |
| `escalation.py` | ✅ |
| `workflow/engine.py` | ✅ 状态机，非可视化 |
| `skills/flows/runner.py` | ✅ 6 flow（含 cleanup、cpu_stress） |

### 5.3 ReAct 上下文治理（2026-05-30 落地）

**问题**：多轮工具调用将完整 `tool.content` 写入 `_history`，且循环内未压缩，首轮 user 含 RAG + 全量感知 + planner，易导致 token 膨胀与超时。

**方案**（`security_agent/agent/react_context.py` + `brain.py` 接线）：

| 机制 | 实现 | 状态 |
|------|------|------|
| 工具观测硬截断 | `truncate_observation` → history / tool_trace | ✅ |
| 首轮 user 瘦身 | `build_react_user_message`（grounding / 感知 / planner 独立上限） | ✅ |
| 每轮后预算 | `apply_history_budget`（tool 截断 → 条数窗口 → `TokenManager.compress_messages`） | ✅ |
| 跨轮对话窗口 | `_trim_history` 委托 `apply_history_budget` | ✅ |
| 末轮收束 | 最后一轮 `tools=None`、`tool_choice=none` | ✅ |
| 工具链输出上限 | `REACT_CHAIN_OUTPUT_MAX_CHARS` 替代硬编码 6000 | ✅ |

**环境变量**（`security_agent/config.py`）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `REACT_MAX_TOOL_ROUNDS` | 8 | ReAct 最大工具轮次（`rules.py` 同步） |
| `REACT_TOOL_OBSERVATION_MAX_CHARS` | 2000 | 单条 tool 写入 history 上限 |
| `REACT_GROUNDING_MAX_CHARS` | 2400 | RAG grounding 块上限 |
| `REACT_PERCEPTION_MAX_CHARS` | 2200 | 环境感知块上限 |
| `REACT_PLANNER_NOTE_MAX_CHARS` | 800 | 编排提示上限 |
| `REACT_CHAIN_OUTPUT_MAX_CHARS` | 3500 | 并行/工具链注入 LLM 的观测上限 |
| `MAX_HISTORY_ROUNDS` | 15 | 跨轮对话保留轮数 |

**验收**：

```bash
.venv/bin/python tests/test_react_context.py
```

---

## 6. Skill 封装落地计划

### 6.1 首批 3 个 L2 Flow

| Flow | 步骤 | 入口 | 状态 | Phase |
|------|------|------|------|-------|
| `secure_exec` | 三层防御评估 → 安全执行 | `run_skill_flow("secure_exec", {command, user_message})` | ✅ REST 已暴露 | — |
| `alert_response` | 告警 → `route_alert_to_skills` | `run_skill_flow("alert_response", {alert_event})` | ✅ REST 已暴露 | — |
| `scan_report` | `run_security_scan` → 格式化报告 | `run_skill_flow("scan_report", {})` | ✅ REST 已暴露 | — |
| `system_cleanup` | 扫描可清理项 → 安全执行 | `run_skill_flow("system_cleanup", {})` | ✅ 新增 | — |
| `cpu_stress` | 多核压测 → 阈值自动停止 | `run_skill_flow("cpu_stress", {mode, duration, threshold})` | ✅ 新增 | — |

### 6.2 落地步骤

| 步骤 | 内容 | 状态 |
|------|------|------|
| S1 | `skills/flows/runner.py` + `run_skill_flow` | ✅ |
| S2 | orchestrator 意图映射（如「一键扫描报告」→ `scan_report`） | ✅ |
| S3 | REST `POST /api/skills/flows/{name}/run` | ✅ |
| S4 | Vue「Skill 流程」页或 Agent 快捷按钮 | ✅ |
| S5 | pytest `tests/test_skill_flows.py` | ✅ |
| S6 | Streamlit `pages_skill_flows.py` 展示 flow 列表 | ✅ |

### 6.3 MCP Skill 与 L2 关系

- **L1 MCP Skill**（healthcheck 等）：独立进程，Brain 经 registry 调用
- **L2 Flow**：进程内 asyncio 步骤链，适合答辩确定性演示
- **不重复封装**：Flow 内部复用 L1 工具，不在 Flow 内再写 MCP 协议

---

## 7. 验收命令清单

### 7.1 后端核心

```bash
# 依赖
uv sync

# 三层防御（6 场景）
.venv/bin/python tests/test_three_layer_defense.py

# 注入与意图
.venv/bin/python tests/test_injection_and_intent.py

# 推理 trace
.venv/bin/python tests/test_reasoning_trace.py

# ReAct 上下文治理
.venv/bin/python tests/test_react_context.py

# 一键回归（单测 + E2E）
bash scripts/run_regression.sh

# P0 API 段（需 boot_start 后）
bash scripts/p0_frontend_checklist.sh

# 冒烟（无 API Key 部分用例）
.venv/bin/python scripts/smoke_test.py
```

### 7.2 API 服务

```bash
uv run uvicorn security_agent.api.app:app --host 0.0.0.0 --port 8000

curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/mcp/servers
curl -s http://127.0.0.1:8000/api/knowledge/playbooks | head
```

### 7.3 前端

```bash
cd frontend
npm install          # node_modules 已存在可跳过
npm run build        # 输出 frontend/dist
npm run dev          # :5173，proxy → :8000
```

### 7.6 API / Vue 联调冒烟

```bash
PYTHONPATH=. .venv/bin/python scripts/e2e_api_smoke.py
```

### 7.4 Streamlit（B1 快速演示）

```bash
bash boot_start.sh   # → http://localhost:8501
```

### 7.5 L2 Flow（Python 直接调用）

```python
import asyncio
from security_agent.skills.flows import run_skill_flow, list_flows

print(list_flows())
asyncio.run(run_skill_flow("scan_report", {}))
```

### 7.6 答辩推荐拓扑

```bash
# 终端 1：API + Vue 静态
uv run uvicorn security_agent.api.app:app --host 0.0.0.0 --port 8000
# 浏览器：http://<主机>:8000/
```

---

## 8. 风险与决策点

### 8.1 技术风险

| 风险 | 等级 | 现状 | 缓解 |
|------|------|------|------|
| Vue 浏览器联调未签字 | 🔴 | API E2E 28/28 已过；缺人工 10 页 | P0 [P0_FRONTEND_WALKTHROUGH.md](../P0_FRONTEND_WALKTHROUGH.md) |
| GAP_ANALYSIS 过时 | ⚠️ | 仍写「无沙箱」 | 以本文 + TECHNICAL 为准 |
| 麒麟 mac_checker 实机未验 | ⚠️ | 已接 executor 钩子；非麒麟放行 | P1 麒麟实机一条 |
| MCP 热插拔 | ✅ | `POST /api/mcp/reload` | — |
| 双前端维护成本 | ⚠️ | Streamlit 全 + Vue 薄 | 答辩主推 B2，Streamlit 作备份 |
| LLM API Key 答辩现场 | ⚠️ | Agent 页依赖 Key | 准备无 Key 演示路径（安全闸门/执行器/扫描） |

### 8.2 需用户决策

| # | 决策 | 选项 | 建议 |
|---|------|------|------|
| D1 | 答辩主前端 | A) Vue B/S :8000  B) Streamlit :8501 | **A**，与赛题 B/S 一致 |
| D2 | qt01 Qt 流程图 | 迁入 / 仅截图 / Vue Flow 只读 | **Vue Flow 只读**（P2），不迁 Qt |
| D3 | Dify 工作流 | 集成 / 不集成 | **不集成**，除非时间充裕 |
| D4 | 多 Agent | 迁入 qt01 multi_agent / 保持单 Brain | **保持单 Brain**，P2 可选 |
| D5 | L2 Flow REST 暴露 | P0 不做 / P1 做 | **P1**，P0 专注 Vue 联调 |
| D6 | 版本号统一 | API `__version__` 与 app 0.7.0 | ✅ 已对齐 0.7.0 |
| D7 | CI | GitHub Actions 跑三层防御单测 | 建议加，非阻塞 P0 |

### 8.3 赛题得分预估（不变）

| 维度 | 预估 |
|------|------|
| MCP 插件丰富度 | 50% |
| 安全校验能力 | 45% → **P1 mac_checker 后可提升** |
| 推理链路可追溯性 | 50% |
| **综合** | **75–90 分**（三层防御 + trace 已补强） |

---

## 9. 文档索引

| 文档 | 用途 |
|------|------|
| **本文 MASTER_PLAN.md** | 总控计划、阶段、矩阵、决策 |
| [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) | 技术分层、数据流、部署 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Streamlit 九页与 Skill 细节 |
| [../A2_ARCHITECTURE_MAPPING.md](../A2_ARCHITECTURE_MAPPING.md) | 赛题得分对照 |
| [../competitions/GAP_ANALYSIS.md](../competitions/GAP_ANALYSIS.md) | 历史缺口（部分过时） |
| [../../frontend/ARCHITECTURE.md](../../frontend/ARCHITECTURE.md) | Vue 路由与 API 约定 |

---

*最后更新：2026-05-30 · 维护者：security-agent 项目组*


## 10. 2026-06-08 重构日志 — 架构清理 + Harness 工程化 + 权限管控

### 10.1 清理死代码

| 操作 | 模块 | 原因 |
|------|------|------|
| 删除 | `optimization/` (13 py) | DI容器/cache/adapters — 0次外部引用 |
| 删除 | `plugins/` (2 py) | 被 skills/registry.py 取代 |
| 删除 | `dify/` (2 py + routes) | P2 可选集成，无实例运行 |
| 删除 | `blue_team_rules/` (8 py) | 空骨架，0 实现 |
| 合并 | `knowledge/mcp/` → `mcp/` | 去重两套 MCP 目录 |
| 删除 | `test_dify_bridge.py`, `test_blue_team_rules.py`, `dify_routes.py` | 关联死代码 |

**结果**: 204 → 177 py 文件 (-13%)

### 10.2 新功能

| 编号 | 功能 | 文件 | 说明 |
|------|------|------|------|
| A | 自动回滚 | `safety_gate/risk.py`, `api/routes/executor_routes.py`, `terminal/executor.py` | SnapshotManager 接线 + `_maybe_auto_rollback()` |
| B | tenacity 重试 | `agent/fallback.py` | LLM 主模型调用指数退避重试 |
| C1 | 网络运维 MCP | `skills/network_ops/` (3 files) | 5 工具: 端口/连接/防火墙/DNS |
| C2 | 磁盘管理 MCP | `skills/disk_manager/` (3 files) | 6 工具: 分区/IO/大文件/可清理/备份 |
| D | 动态阈值 | `monitor/dynamic_threshold.py` | 移动平均+标准差自适应（Prometheus 端点: `api/routes/metrics_routes.py`）|
| E | Gitee Wiki 知识库 | `knowledge/gitee_wiki/` (6 files) | API v5 客户端 + TF-IDF 向量索引 + MCP Server + 同步脚本 |
| F | 语义记忆系统 | `memory/semantic_memory.py` | Mem0 风格 L1/L2/L3 三级记忆 |
| G | 自验证循环 | `agent/brain.py:_verify_result()` | PID/端口幻觉检测 + 知识库交叉校验 |
| H | 实时流程泳道 | `api/routes/workflow_routes.py:flow-status` | 四泳道聚合端点 |
| I | 无限画布 | `frontend/src/views/InfiniteCanvas.vue` | 运维态势可视化画布 |
| J | 任务分发引擎 | `ops/task_dispatch.py` | 权限管控 + 沙箱预演 + 封装内部指令 |
| K | 快照管理 API | `api/routes/executor_routes.py` | GET/POST/DELETE /snapshots + 真实文件恢复 |

### 10.3 前端重构

| 改动 | 说明 |
|------|------|
| 侧边栏分组 | 11项扁平 → 4组 7项 (总览/安全管控/能力审计/知识) |
| SafetyGate ↔ Executor 打通 | 评估通过 → 绿色按钮跳转执行；执行页顶部横幅"已通过三层防御" |
| WorkflowView 重写 | 泳道实时视图 + 3 Tab (实时流程/工作流模板/Skill目录) |
| 无限画布 | `/canvas` 路由，节点+连线+双击展开+实时数据 |
| 隐藏路由 | `/flows`, `/workflow`, `/blue-team` 保留可访问但不出现在侧边栏 |

### 10.4 Harness Engineering 六大模块对照

| 模块 | 对标实现 | 完成度 |
|------|---------|--------|
| ① 上下文架构 | `react_context.py` 截断+瘦身 | 80% |
| ② 架构约束 | `task_dispatch.py` 权限白名单 + `three_layer_defense.py` | 100% |
| ③ 自验证循环 | `_verify_result()` PID幻觉检测+知识库交叉 | 85% |
| ④ 上下文隔离 | 单Agent够用 | 60% |
| ⑤ 熵治理 | `sync_gitee_wiki.sh` + `clean_old_snapshots(72h)` | 80% |
| ⑥ 可拆卸模块化 | MCP热插拔 + 17 Skills + L1/L2/L3 | 100% |

### 10.5 当前模块统计

```
security_agent/        177 py
├── agent/             18 py   (脑、编排、回退、自验证)
├── api/               28 py   (FastAPI + 路由 + WS)
├── audit/              9 py   (事件脊柱、Trace、JSONL日志)
├── auth/               5 py   (JWT + RBAC)
├── confirm/            2 py   (S4 审批队列)
├── demo/               7 py   (竞赛演练场景)
├── knowledge/         12 py   (+ gitee_wiki/ 6 files)
├── mcp/                3 py   (统一MCP注册中心)
├── memory/             3 py   (对话记忆 + 语义记忆)
├── monitor/            8 py   (巡检 + 动态阈值)
├── notify/             2 py   (离屏告警)
├── ops/                3 py   (守卫 + 任务分发)
├── resilience/         4 py   (预算、熔断、降级)
├── retrieval/          2 py   (混合检索: Playbook+Wiki)
├── rules/              2 py   (规则引擎)
├── safety_gate/        7 py   (三层防御、快照、注入、MAC检查)
├── scanner/            2 py   (安全扫描)
├── security/           2 py   (脱敏)
├── skills/            41 py   (17 Skills: 含新增 network_ops/disk_manager)
├── storage/            3 py   (快照+Trace 持久化)
├── terminal/           4 py   (Executor + PrivilegeBroker + Sandbox)
├── tools/              4 py   (工具注册中心)
├── utils/              2 py   (Token管理)
├── visualizer/         2 py   (Trace可视化)
└── workflow/           2 py   (状态机引擎)
```

### 10.6 前端页面矩阵 (2026-06-09)

| 路由 | 页面 | 侧边栏 | 定位 |
|------|------|--------|------|
| `/` | Dashboard.vue | 📊 总览 | 抽屉式折叠布局 · 系统指标 · Agent 评估(v2) |
| `/agent` | AgentChat.vue | 📊 总览 | LLM 对话 + 命令芯片(点击→安全执行) |
| `/canvas` | InfiniteCanvas.vue | 📊 总览 | 五层架构闭环画布 (19节点+21连线+实时) |
| `/safety` | SafetyGate.vue | ⚙️ 安全管控 | **合并版**: 输入→评估→执行 (含自动回滚展示) |
| `/alerts` | Alerts.vue | ⚙️ 安全管控 | 5s 自动轮询 |
| `/mcp` | MCPManage.vue | 🔧 能力审计 | 17 Skills 管理 |
| `/trace` | TraceView.vue | 🔧 能力审计 | 8s 自动轮询 · 时间线/DAG/热力图 |
| `/knowledge` | Knowledge.vue | 📚 知识 | Facet 多维结构化搜索 |
| `/guide` | GuidePage.vue | 📚 知识 | 技术导引 · 赛题架构 · 快速入门 |
| — | — | — | — |
| `/executor` | Executor.vue | **隐藏** | 已合并到 SafetyGate |
| `/flows` | SkillFlows.vue | **隐藏** | Skill Flow 测试 |
| `/workflow` | WorkflowView.vue | **隐藏** | 旧工作流页 |
| `/blue-team` | BlueTeam.vue | **隐藏** | 蓝队知识 |
| `/users` | Users.vue | **隐藏(admin)** | 用户管理 |

### 10.7 评估模型 v2

| 特性 | 旧 (v1) | 新 (v2) |
|------|---------|---------|
| 聚合 | 加权和 | 几何平均 (避免短板被掩盖) |
| 维度 | 5 | 6 (新增知识相关度) |
| 小样本 | 1次失败=全面F | Wilson 置信区间下界 + 贝叶斯收缩 |
| 安全漏报 | 权重扣分 | 硬约束: 所有维度 ×0.85 |
| 趋势 | 无 | improving/stable/declining |
| Token | 仅累计 | 线性回归预测 + 方向判定 |

### 10.8 后端模块现状 (181 py)

```
agent/   19py   Brain · Orchestrator · Fallback · evaluation(v2)
api/     29py   FastAPI + 路由 + WS + eval_routes
audit/    9py   IncidentSpine · Trace · 六阶段
knowledge/10py  Playbooks(53条) · Gitee Wiki(27篇) · seed
retrieval/ 3py  knowledge_index(多维Facet) · hybrid
skills/  41py   17 Skills (network_ops/disk_manager)
safety_gate/8py 三层防御 · 快照 · 注入 · mac_checker
terminal/ 4py   Executor · PrivilegeBroker · Sandbox (_maybe_auto_rollback)
resilience/4py  预算·熔断·降级 S0-S4
monitor/  8py   巡检 + 动态阈值
memory/   3py   ConversationMemory + SemanticMemory(Mem0)
ops/      3py   Guardrails + TaskDispatch(权限管控)
data/     agent_eval.json · wiki_cache · snapshots/ · alerts/

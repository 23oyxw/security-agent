# 技术架构总览 v0.7.0

> **定位**：银河麒麟智能安全运维 Agent（A2 赛题）——以 `security-agent` 为主干，FastAPI 为核心服务层，Streamlit / Vue3 双前端可选，qt01 为赛题能力参考库。  
> **更新**：2026-05-30  
> **关联**：[MASTER_PLAN.md](MASTER_PLAN.md)（总控计划）· [TECH_STACK.md](TECH_STACK.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [A2_ARCHITECTURE_MAPPING.md](../A2_ARCHITECTURE_MAPPING.md)

---

## 1. 三条交付线（区分度）

本项目存在 **三条可独立演进、通过 API 解耦** 的交付线，职责不重叠：

| 交付线 | 路径 | 角色 | 状态 |
|--------|------|------|------|
| **A. 核心后端** | `security_agent/` | 赛题五大支柱、安全闸门、Agent、MCP、审计 | ✅ 主交付 |
| **B. Web 控制台** | `frontend/`（Vue3）+ `streamlit_app.py` + `ui/` | 人机交互、答辩演示 | ⚠️ 双轨并行，Vue 待联调 |
| **C. 赛题参考库** | `qt01/` | Qt 流程图、Dify、完整 pytest，**不并入主干** | 📦 只读参考 |

```text
                    ┌─────────────────────────────────────┐
                    │         C. qt01（参考库，不部署）       │
                    │  qt-security-flow / dify_integration │
                    └──────────────────┬──────────────────┘
                                       │ 能力已择优迁入 A
┌──────────────┐   REST/WS    ┌───────▼────────────────────────┐
│ B1 Streamlit │─────────────►│  A. security_agent + FastAPI     │
│  :8501       │  直连 Python  │  :8000 / :8600                  │
├──────────────┤              │  五大支柱 API + Agent + SafetyGate │
│ B2 Vue3 SPA  │─── Axios ──►│                                  │
│  :5173 dev   │              └───────────────┬──────────────────┘
└──────────────┘                              │
                                              ▼
                                    OS / 麒麟 / 文件 data/
```

**整合原则**：新能力先进 **A**，B 只调 API；qt01 **不复制整包**，只迁移赛题得分模块。

---

## 2. 分层架构与解耦边界

### 2.1 逻辑分层

```text
┌─────────────────────────────────────────────────────────────────┐
│ 表现层 Presentation                                              │
│  Streamlit(ui/)  │  Vue3(frontend/)  │  MCP Client / IDE        │
│  耦合方式：import  │  HTTP /api/*      │  stdio MCP              │
└────────────────────────────┬────────────────────────────────────────┘
                             │ 仅通过公开接口
┌────────────────────────────▼────────────────────────────────────────┐
│ API 网关层  security_agent/api/                                       │
│  认证 JWT │ 路由分五大支柱 │ CORS │ 静态资源 frontend/dist            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ 编排层 Orchestration                                                │
│  agent/orchestrator  agent/brain  agent/autonomous                  │
│  workflow/engine（自主任务状态机，非可视化编辑器）                      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ 安全控制层     │  │ 能力层           │  │ 感知与数据层      │
│ safety_gate/  │  │ tools/ skills/  │  │ monitor/ scanner/│
│ rules/        │  │ knowledge/      │  │ terminal/ audit/ │
│ confirm/      │  │ retrieval/      │  │ storage/ data/   │
└───────────────┘  └─────────────────┘  └─────────────────┘
```

### 2.2 解耦规则（强制）

| 规则 | 说明 |
|------|------|
| **UI 不 import 业务** | Vue / Streamlit 禁止 `from security_agent.agent import ...`，只调 `/api/*` 或封装好的 client |
| **安全先于执行** | 写操作必经 `SafetyGate` 或 `ThreeLayerDefenseEngine`，再进 `terminal/executor` |
| **事件脊柱** | `audit/spine.py`：`TraceContext` + `ReasoningTrace` + `RequestBudget` 同一 `trace_id`；`GET /api/trace/{id}/export` 导出卷宗 |
| **弹性** | `resilience/`：超时预算树、依赖熔断（`llm:*`/`dify:proxy`）、S0–S2 降级阶梯 |
| **工具双注册** | `tools/registry.py`（原始工具）+ `skills/registry.py`（MCP Skill），合并暴露给 Brain |
| **Skill 三层封装** | L1 原子工具/MCP → L2 `skills/flows/` 多步 flow → L3 `agent/orchestrator` 胶水；详见 [MASTER_PLAN.md §2](MASTER_PLAN.md#2-解耦与-skill-封装分层l1--l2--l3) |
| **配置单入口** | 主干用 `security_agent/config.py`；禁止与 qt01 的 `config/` 包混用 |
| **qt01 隔离** | `qt01/` 不参与 `uv run`、不参与 CI 默认路径 |

### 2.3 Skill 封装分层（L1 / L2 / L3）

| 层级 | 路径 | 职责 | 状态 |
|------|------|------|------|
| **L1** | `tools/`、`skills/*/skill.py`、MCP server | 单步原子能力 | ✅ |
| **L2** | `skills/flows/runner.py` | 确定性多步 flow（`secure_exec` / `alert_response` / `scan_report`） | ⚠️ 脚手架，`run_skill_flow()` 可用 |
| **L3** | `agent/orchestrator.py`、`brain.py` | LLM 意图路由、trace 贯穿、调用 L2 | ✅ |

UI 与 L2 之间建议经 REST（P1：`POST /api/skills/flows/{name}/run`），当前仅 Python 直调。

---

## 3. 五大支柱 ↔ 模块 ↔ API 对照

| 赛题支柱 | 核心模块 | REST 前缀 | 完成度 |
|----------|----------|-----------|--------|
| ① OS 环境深度感知 | `scanner/` `monitor/` `agent/perception.py` | `/api/perception` `/api/monitor` | ✅ 已实现 |
| ② MCP 插件化 | `tools/` `skills/*/mcp_server.py` `knowledge/mcp/` | `/api/mcp` | ✅ 已实现；⚠️ 热插拔未做 |
| ③ 安全意图校验 | `safety_gate/` `rules/` | `/api/safety` | ✅ 已实现（含三层防御） |
| ④ 最小权限执行 | `terminal/privilege.py` `terminal/sandbox.py` | `/api/executor` | ✅ 已实现 |
| ⑤ 推理链路溯源 | `audit/trace.py` `audit/reasoning_trace.py` | `/api/trace` `/api/audit` | ✅ 已实现 |

---

## 4. 模块完成度矩阵

图例：**✅ 完成** · **⚠️ 部分** · **❌ 未做** · **📦 仅在 qt01**

### 4.1 安全控制层 `safety_gate/`

| 模块 | 说明 | 状态 | 来源 |
|------|------|------|------|
| `gate.py` | SafetyGate 单闸门编排 | ✅ | 主干 |
| `risk.py` | 四级风险矩阵 | ✅ | 主干 |
| `intent.py` | 意图偏离审计 | ✅ | 主干 |
| `snapshot.py` | 快照备份回滚 | ✅ | 主干 |
| `three_layer_defense.py` | L1/L2/L3 加权 30/35/35 | ✅ | 自 qt01 迁入 |
| `injection_defense.py` | 五类注入检测 | ✅ | 自 qt01 迁入 |
| `mac_checker.py` | 麒麟 KYSEC/SELinux | ✅ | `terminal/executor.py` 执行前钩子 |
| `orchestrator.run_with_three_layer_defense` | 统一安全执行入口 | ✅ | 主干封装 |

### 4.2 Agent 与编排 `agent/`

| 模块 | 说明 | 状态 |
|------|------|------|
| `brain.py` | LLM 多轮对话 + 工具调用 | ✅ |
| `orchestrator.py` | 意图识别 + 计划 + 三层防御执行 | ✅ |
| `autonomous.py` | Plan-Execute 自主运维 | ✅ |
| `escalation.py` | 告警升级与自愈 | ✅ |
| `perception.py` | 环境采集 | ⚠️ 偏被动，缺请求时自动探测 |
| `reasoning_engine.py` | ReAct/Plan-Execute 策略选择 | 📦 qt01 |
| `multi_agent.py` | 六 Agent 协作 | 📦 qt01 |

### 4.3 执行与终端 `terminal/`

| 模块 | 说明 | 状态 |
|------|------|------|
| `privilege.py` | PrivilegeBroker 最小权限 | ✅ |
| `sandbox.py` | setuid/资源限制沙箱 | ✅ |
| `executor.py` | 规则校验 → 沙箱/降权执行 | ✅ |

### 4.4 审计 `audit/`

| 模块 | 说明 | 状态 |
|------|------|------|
| `log.py` | JSONL 审计日志 | ✅ |
| `trace.py` | TraceContext 6 阶段 | ✅ |
| `reasoning_trace.py` | 思考/操作/安全/知识全记录 | ✅ |

### 4.5 MCP 与 Skills

| 模块 | 说明 | 状态 |
|------|------|------|
| 5 个 Skill 包 | healthcheck / log_analyzer / … | ✅ |
| `skills/*/mcp_server.py` | stdio MCP 独立进程 | ✅ |
| `mcp/registry.py` | 运行时热插拔（reload / manifest） | ✅ |
| `mcp/plugin_manager.py` (qt01 完整版) | 重型注册中心 | 📦 qt01 |
| 工具总数 | ~23 原始 + ~26 Skill | ✅ |

### 4.6 工作流与可视化

| 能力 | 主干 | qt01 | 建议 |
|------|------|------|------|
| 自主任务状态机 | `workflow/engine.py` ✅ | `execution_controller.py` 📦 | 主干够用 |
| Qt 流程图编辑器 | ❌ | `qt-security-flow/` 📦 | 答辩备选，不并入 |
| Dify 可视化工作流 | ❌ | `dify_integration/` 📦 | V2 可选 |
| Vue 只读流程图 | ❌ | — | V2 用 Vue Flow |
| Web 拖拽编排 | ❌ | — | **不做**（性价比低） |

### 4.7 前端交付线

| 项目 | 技术栈 | 状态 | 说明 |
|------|--------|------|------|
| Streamlit 控制台 | Streamlit + Plotly | ✅ 可用 | `boot_start.sh` → :8501，功能最全 |
| Vue3 SPA | Vue3 + Vite + Element Plus + Pinia | ⚠️ 骨架完成 | 10 个页面已建，**API 部分未对齐** |
| FastAPI 静态托管 | `app.py` mount `frontend/dist` | ⚠️ | 需 `npm run build` 后生效 |

#### Vue 页面联调状态

| 路由 | 页面 | API 对接 | 状态 |
|------|------|----------|------|
| `/login` | Login.vue | `/api/auth/login` | ⚠️ 待验 |
| `/` | Dashboard.vue | perception + alerts | ⚠️ 待验 |
| `/agent` | AgentChat.vue | `/api/agent/chat` | ⚠️ 待验 |
| `/safety` | SafetyGate.vue | `POST /api/safety/defense/evaluate` | ✅ 已对齐 |
| `/executor` | Executor.vue | `POST /api/executor/execute` | ✅ 已对齐 |
| `/trace` | TraceView.vue | `GET /api/trace/` | ✅ 已对齐 |
| `/mcp` | MCPManage.vue | `GET /api/mcp/servers` | ✅ 已对齐 |
| `/alerts` | Alerts.vue | `GET /api/alerts/` | ✅ 已对齐 |
| `/knowledge` | Knowledge.vue | `GET /api/knowledge/playbooks` | ✅ 已对齐 |
| `/users` | Users.vue | `GET /api/auth/users` | ✅ 已对齐 |

---

## 5. 技术栈整合（当前主干）

### 5.1 后端

| 层次 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | ≥ 3.10 |
| 包管理 | uv | — |
| API | FastAPI + Uvicorn | ≥ 0.115 |
| 认证 | PyJWT + passlib | — |
| LLM | OpenAI 兼容 + LiteLLM（可选） | — |
| MCP | mcp (stdio) + FastMCP | ≥ 1.27 |
| 存储 | JSONL + SQLite + `data/` 文件 | 无独立 DB 服务 |

### 5.2 前端（目标栈 · 已初始化）

| 层次 | 技术 | 状态 |
|------|------|------|
| 框架 | Vue 3 组合式 API | ✅ `frontend/` |
| 构建 | Vite 5 | ✅ |
| UI | Element Plus 2.7 | ✅ |
| 状态 | Pinia 2 | ✅（仅 user store） |
| 路由 | Vue Router 4 | ✅ |
| HTTP | Axios | ✅ 统一封装 `api/index.js` |
| 图表 | ECharts + vue-echarts | ✅ Dashboard 使用 |

### 5.3 弃用 / 不采用

| 技术 | 原因 |
|------|------|
| Bootstrap + Webpack | 与 Vue3/Vite 栈冲突，维护成本高 |
| 第三套 UI（Qt）并入主干 | 与 Vue B/S 定位重复，保留在 qt01 |
| 第一期可视化工作流编辑器 | 赛题非核心，开发量大 |

---

## 6. 关键数据流

### 6.1 用户对话（Streamlit 或 Vue → Agent）

```text
用户输入
  → POST /api/agent/chat  (Vue)  或  AgentBrain.chat() (Streamlit 直连)
  → orchestrator.build_plan / tools.registry
  → check_tool / SafetyGate（工具级）
  → terminal/executor（若含 shell）
  → audit.log + reasoning_trace
  → 响应返回前端
```

### 6.2 高危命令（三层防御 + 沙箱）

```text
命令 + 用户原话
  → ThreeLayerDefenseEngine.evaluate()  或  POST /api/safety/defense/evaluate
      L1 静态风险 30% + 注入检测
      L2 意图审计 35%
      L3 受限环境 35%
  → verdict: allow | confirm | deny | quarantine
  → run_with_three_layer_defense() / POST /api/executor/execute
  → sandbox (REVERSIBLE+) 或 privilege (READONLY)
  → data/audit.log + data/traces/*.jsonl
```

### 6.3 MCP 插件调用

```text
Brain 工具列表 ← tools/registry + skills/registry
  → call_tool_local() 或 独立 mcp_server 子进程
  → safety_gate（按工具风险）
  → 执行 + 审计
```

---

## 7. 目录职责（主干）

```text
security-agent/
├── security_agent/          # A. 核心后端（唯一业务源码）
├── frontend/                # B2. Vue3 SPA（仅 HTTP 耦合）
├── ui/ + streamlit_app.py   # B1. Streamlit（开发期可直连 Python）
├── configs/                 # 外部 YAML/JSON
├── data/                    # 运行时数据（审计、告警、快照、trace）
├── scripts/                 # 运维与验收脚本
├── tests/                   # pytest（三层防御等）
├── docs/                    # 文档
└── qt01/                    # C. 参考库（不部署、不 import）
```

---

## 8. 部署拓扑（麒麟适配）

| 模式 | 命令 | 端口 | 适用 |
|------|------|------|------|
| Streamlit 单机 | `bash boot_start.sh` | 8501 | 开发、快速演示 |
| API only | `uv run uvicorn security_agent.api.app:app --port 8000` | 8000 | Vue 联调 |
| Vue 开发 | `cd frontend && npm run dev` | 5173 → proxy 8600 | 前端开发 |
| 生产 B/S | API + `frontend/dist` 静态挂载 | 8000 单端口 | 答辩推荐 |

麒麟注意：Vite 构建为静态文件，浏览器用系统 Chromium/Firefox；无需 Node 运行时上生产机。

---

## 9. 近期优先级（与架构对齐）

| 优先级 | 任务 | 归属 |
|--------|------|------|
| P0 | Vue `SafetyGate.vue` 对接 `/api/safety/defense/evaluate` | ✅ frontend |
| P0 | `npm run build` + FastAPI 静态托管验证 | ✅ dist 已构建 |
| P1 | Vue 各页 API 字段与 `api/models.py` 对齐 | frontend |
| P1 | `mac_checker` 接入 executor 执行前钩子 | safety_gate |
| P2 | Pinia 拆分 stores（alerts / agent / safety） | frontend |
| P2 | 只读流程图页（Vue Flow）展示预置 JSON | frontend |
| P3 | 从 qt01 择优迁入 `mcp/plugin_manager.py` | 后端 |

---

## 10. 验证命令

```bash
# 三层防御（6 场景）
.venv/bin/python tests/test_three_layer_defense.py

# API 健康
uv run uvicorn security_agent.api.app:app --port 8000
curl http://127.0.0.1:8000/api/health

# Streamlit
bash boot_start.sh

# Vue 开发
cd frontend && npm install && npm run dev
```

---

## 11. 文档索引

| 文档 | 内容 |
|------|------|
| [MASTER_PLAN.md](MASTER_PLAN.md) | **总控计划**：阶段路线图、矩阵、验收、决策点 |
| **本文** | 总架构、完成度、解耦、三交付线 |
| [TECH_STACK.md](TECH_STACK.md) | 依赖版本与自研模块清单 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Streamlit 九页与 Skill 细节 |
| [../A2_ARCHITECTURE_MAPPING.md](../A2_ARCHITECTURE_MAPPING.md) | 赛题得分点对照 |
| [../competitions/GAP_ANALYSIS.md](../competitions/GAP_ANALYSIS.md) | 历史缺口与 P0 清单 |
| [../../frontend/package.json](../../frontend/package.json) | Vue 依赖锁定 |

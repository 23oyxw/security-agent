# 技术架构总览 v0.9.0

> **定位**：银河麒麟智能安全运维 Agent（A2 赛题）——以 `security-agent` 为主干（260 py, 34 模块），FastAPI 为服务层，Vue3 :8900 为主前端。  
> **更新**：2026-07-15  
> **Agent 编排权威**：[FINAL_ARCHITECTURE.md](FINAL_ARCHITECTURE.md)（终版三 Agent + 五层流水线 · 先分析后执行 · 计划/执行双模式）  
> **关联**：[MASTER_PLAN.md](MASTER_PLAN.md) · [TECH_STACK.md](TECH_STACK.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [A2_ARCHITECTURE_MAPPING.md](../A2_ARCHITECTURE_MAPPING.md)

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

## 2. 五层智能体流水线（运行时编排）

> 完整定义见 **[FIVE_LAYER_PIPELINE.md](FIVE_LAYER_PIPELINE.md)**。以下为与技术栈对齐的摘要。

### 2.0 设计约束（强制）

| 约束 | 说明 |
|------|------|
| 先分析后执行 | 任何用户指令/流程/批量操作必须先经 **L1 分析计划** |
| L1/L2 不决策 | 第一、二层只感知与管控，**禁止**直接调用写操作 MCP/executor |
| Agent 复用 | L1 分析计划与 L3 推理分发 **共用同一 Agent**（`mode=plan\|execute`） |
| MCP+Flow 一体 | 原子 MCP 工具与封装流程 **同一注册模块**，热插拔、统一审计 |
| 知识在 Wiki | 边界对抗数据、规范知识库、知识回流 → **Gitee Wiki** |

### 2.1 五层总览

```text
用户输入 → L1 感知计划 → L2 安全管控(+沙箱) → L3 推理分发 → L4 审计回流 → L5 数学分析
           │并行│           │并排│              │MCP+Flow│      │trace+Wiki│   │指标+绘图│
           不执行           不执行              可执行          高要求审计
```

| 层 | 名称 | 核心能力 | 主干模块 |
|----|------|----------|----------|
| **L1** | 感知与计划 | 分析计划 · 边界感知 · 知识检索 · 静态感知 · 意图识别 | `agent/` `knowledge/` `monitor/` `scanner/` `demo/boundary` |
| **L2** | 安全管控 | 护栏/兜底/熔断/热插拔/高危截断/确认/CPU弹窗 ∥ 沙箱试跑 | `safety_gate/` `resilience/` `terminal/sandbox` `mcp/registry` |
| **L3** | 推理分发执行 | MCP 工具 + 封装流程（metrics/logs/repair/schedule） | `agent/orchestrator` `mcp/` `skills/flows/` `tools/` |
| **L4** | 审计与回流 | 审计分析 · trace_id 追溯 · 案例打标 → Gitee Wiki | `audit/` `knowledge/reflux`（目标） |
| **L5** | 链路分析迭代 | 散点/热力/溯源 · 六维指标 · 集成测试 | `l5/analytics.py` · `api/routes/l5_routes.py` |

### 2.2 逻辑分层（与五层正交）

```text
┌─────────────────────────────────────────────────────────────────┐
│ 表现层 Presentation                                              │
│  Streamlit(ui/)  │  Vue3(frontend/)  │  MCP Client / IDE        │
│  Agent 主界面：计划模式 / 执行模式 · 批量指令（先分析后执行）      │
└────────────────────────────┬────────────────────────────────────────┘
                             │ 仅通过公开接口
┌────────────────────────────▼────────────────────────────────────────┐
│ API 网关层  security_agent/api/                                       │
│  L1–L5 分路由 │ JWT │ CORS │ 执行闸门 middleware                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ 五层编排层（见 FIVE_LAYER_PIPELINE.md）                               │
│  L1 plan → L2 gate → L3 dispatch → L4 audit → L5 analytics          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ L2 安全控制    │  │ L3 能力层        │  │ L1/L5 感知数据   │
│ safety_gate/  │  │ mcp+flows/tools │  │ monitor/scanner │
│ resilience/   │  │ terminal/exec   │  │ knowledge/wiki  │
└───────────────┘  └─────────────────┘  └─────────────────┘
```

### 2.3 解耦规则（强制）

| 规则 | 说明 |
|------|------|
| **UI 不 import 业务** | Vue / Streamlit 禁止 `from security_agent.agent import ...`，只调 `/api/*` |
| **L1/L2 执行闸门** | API middleware：无 `plan_id` + L2 pass 则 **拒绝** L3 写操作 |
| **安全先于执行** | L3 写操作必经 L2 `SafetyGate` / `ThreeLayerDefense`，再进 executor |
| **事件脊柱** | `audit/spine.py`：全层同一 `trace_id`；L4 卷宗导出 |
| **弹性** | L2：`resilience/` 超时预算、熔断、S0–S2 降级 |
| **MCP+Flow 一体** | `mcp/registry` + `skills/flows` 统一 manifest 与热插拔 |
| **工具单一职责** | metrics / logs / repair / schedule 四类，一工具一事 |
| **知识 Wiki 源** | 边界对抗、规范库、回流案例 → Gitee Wiki（本地索引缓存） |
| **配置单入口** | `security_agent/config.py` |
| **qt01 隔离** | 不参与默认 CI/部署 |

### 2.4 Skill 封装与 L3 关系（L1 原子 / L2 流程 / L3 分发）

| 层级 | 路径 | 在五层流水线中的位置 | 状态 |
|------|------|----------------------|------|
| **L1 原子** | `tools/`、`skills/*/skill.py`、MCP server | L3 可调用的最小单元；L1 层 **仅只读** 感知类 | ✅ |
| **L2 流程** | `skills/flows/runner.py` | L3 封装流程；L2 沙箱可 dry-run | ⚠️ |
| **L3 分发** | `agent/orchestrator.py`、`brain.py` | Plan/Execute 模式；与 L1 共用 Agent | ⚠️ 需 mode 显式化 |

---

## 3. 五层 ↔ 赛题五大支柱 ↔ API 对照

> 支柱 = 能力域；五层 = 运行时阶段。详见 [FIVE_LAYER_PIPELINE.md §6](FIVE_LAYER_PIPELINE.md#6-与-a2-五大支柱对照)。

| 赛题支柱 | 五层主落点 | 核心模块 | REST 前缀 | 完成度 |
|----------|------------|----------|-----------|--------|
| ① OS 深度感知 | **L1** 静态感知 + **L5** 绘图 | `scanner/` `monitor/` `perception.py` | `/api/perception` | ⚠️ L1 并行编排待统一 |
| ② MCP 插件化 | **L3**（L2 热插拔） | `mcp/` `skills/` `tools/` | `/api/mcp` | ✅ 热插拔已有 |
| ③ 安全意图校验 | **L2** 安全控制 | `safety_gate/` `rules/` | `/api/safety` | ✅ |
| ④ 最小权限执行 | **L2** 沙箱 + **L3** | `terminal/sandbox` `executor` | `/api/executor` | ✅ |
| ⑤ 推理链路溯源 | **L4** | `audit/trace` `spine` | `/api/trace` | ✅ 回流 Wiki ⚠️ |

### 3.1 目标 API（按层）

| 层 | 关键端点 | 状态 |
|----|----------|------|
| L1 | `POST /api/agent/plan` · `/api/boundary/evaluate` · `/api/perception/static` | ⚠️ 规划中 |
| L2 | `POST /api/safety/defense/evaluate` · `/api/sandbox/dry-run` | ⚠️ 后者待建 |
| L3 | `POST /api/agent/execute` · `/api/skills/flows/{name}/run` | ⚠️ chat 待拆分 |
| L4 | `GET /api/trace/{id}` · `POST /api/knowledge/reflux` | ⚠️ reflux 待建 |
| L5 | `GET /api/analytics/*` | ❌ |

---

## 4. 模块完成度矩阵（按五层）

图例：**✅ 完成** · **⚠️ 部分** · **❌ 未做** · **📦 仅在 qt01**

### 4.1 L2 安全控制层 `safety_gate/`

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

### 4.2 L1/L3 Agent 与编排 `agent/`

| 模块 | 说明 | 五层 | 状态 |
|------|------|------|------|
| `brain.py` | LLM 对话 + 工具调用 | L1 plan / L3 execute 共用 | ⚠️ 需 mode 拆分 |
| `orchestrator.py` | 意图识别 + 计划 + 分发 | L1 + L3 | ✅ |
| `autonomous.py` | Plan-Execute 自主运维 | L1→L3 链 | ✅ |
| `perception.py` | 静态感知采集 | L1 | ⚠️ 需并行编排 |
| `escalation.py` | 告警升级 | L2 CPU 弹窗 | ✅ |

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

### 4.5 L3 MCP、Flow 与工具（一体模块）

| 模块 | 说明 | 工具域 | 状态 |
|------|------|--------|------|
| `tools/registry` | 原始工具 | metrics/logs/repair/schedule 待分组 | ⚠️ |
| `skills/*/mcp_server.py` | stdio MCP | 同上 | ✅ |
| `skills/flows/` | 封装流程 | L3 与 MCP 同 manifest | ⚠️ |
| `mcp/registry.py` | 热插拔 reload | L2 | ✅ |

**目标工具域**：指标 · 日志 · 故障修复 · 资源调度 — **单一工具单一职责**。

### 4.6 L4 审计 `audit/`

| 模块 | 说明 | 状态 |
|------|------|------|
| `log.py` | JSONL 审计（高要求 append-only） | ✅ |
| `trace.py` | TraceContext 六阶段 | ✅ |
| `reasoning_trace.py` | 全链路推理记录 | ✅ |
| `knowledge/reflux` | 案例打标 → Gitee Wiki | ❌ 目标 |

### 4.7 L5 链路分析 `security_agent/l5/`

> 完整方案 → [L5_ANALYTICS.md](L5_ANALYTICS.md)

| 能力 | 说明 | 状态 |
|------|------|------|
| 散点离群 | 3σ + IQR · `/api/l5/scatter` | ✅ |
| 热力矩阵 | 时间×服务 · `/api/l5/heatmap` | ✅ |
| 链路溯源 | Span 根因 · `/api/l5/root-cause/{id}` | ✅ |
| 六维量化 | `/api/eval/score` + `l5-metrics.js` | ✅ |
| 集成测试 | `/api/l5/integration/*` | ✅ |
| 前端专属页 | `/l5` L5Analytics.vue | ✅ |

### 4.8 工作流与可视化

| 能力 | 主干 | qt01 | 建议 |
|------|------|------|------|
| 五层泳道 UI | `WorkflowView.vue` | — | 对齐 L1–L5 |
| 自主任务状态机 | `workflow/engine.py` | 📦 | L3 辅助 |
| Qt/Dify 拖拽编排 | ❌ | 📦 | **不做** |

### 4.9 前端交付线（计划/执行双模式）

| 项目 | 技术栈 | 状态 | 说明 |
|------|--------|------|------|
| Vue3 Agent 主界面 | AgentChat.vue | ⚠️ | **计划/执行双模式** · 批量先分析后执行 |
| Vue3 五层泳道 | WorkflowView.vue | ⚠️ | 对齐 L1–L5 可视化 |
| Streamlit | Plotly | ✅ | 开发期全功能 |
| FastAPI 静态托管 | `frontend/dist` | ✅ | :8900 |

#### Vue 页面 ↔ 五层映射

| 路由 | 页面 | 五层 | API |
|------|------|------|-----|
| `/agent` | AgentChat | L1 plan / L3 execute | `/api/agent/plan` · `/api/agent/execute` |
| `/` | Dashboard | 运维概览 | `/api/perception/*` |
| `/l5` | L5Analytics | L5 散点/热力/溯源/集成测试 | `/api/l5/*` · `/api/eval/score` |
| `/safety` | SafetyGate | L2 安全控制 | `/api/safety/*` |
| `/workflow` | WorkflowView | L1–L5 全景 | `/api/workflow/*` |
| `/mcp` | MCPManage | L3 MCP+Flow | `/api/mcp/*` |
| `/trace` | TraceView | L4 审计 | `/api/trace/*` |
| `/knowledge` | Knowledge | L1 检索 + L4 回流 | `/api/knowledge/*` |
| `/alerts` | Alerts | L2 CPU 弹窗 | `/api/alerts/*` |

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

## 6. 关键数据流（五层）

### 6.1 标准用户指令（先分析后执行）

```text
用户输入（指令/流程/批量）
  → POST /api/agent/plan          [L1]
      parallel: boundary_perception + knowledge_search + static_perception
      → intent + AnalysisPlan（只读，无写操作）
  → 前端「计划模式」展示 → 用户确认
  → POST /api/safety/defense/evaluate  [L2 安全控制]
  → POST /api/sandbox/dry-run（可选）  [L2 沙箱]
  → verdict pass/confirm
  → POST /api/agent/execute       [L3]（mode=execute, plan_id）
      → MCP 工具 / 封装 flow（metrics|logs|repair|schedule）
      → executor（写操作）
  → audit/spine + trace           [L4]
  → POST /api/knowledge/reflux    [L4 → Gitee Wiki]
  → GET /api/analytics/*          [L5]
```

### 6.2 高危命令（L2 三层防御 + L3 沙箱执行）

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

### 6.3 L3 MCP + Flow 一体调用

```text
Brain（execute 模式）← unified manifest（tools + flows）
  → 按域选工具：metrics | logs | repair | schedule
  → L2 二次 SafetyGate
  → call_tool_local / mcp_server 子进程
  → L4 audit + trace_id
```

### 6.4 知识库（Gitee Wiki）

```text
L1 检索 ← sync ← Gitee Wiki（规范 + 边界对抗集）
L4 回流 → 案例解析 → 打标 → push Gitee Wiki → 重建本地索引
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
| Vue3 生产 | `bash boot_start.sh` | 8900 | 答辩演示 |
| API only | `uvicorn security_agent.api.app:app --port 8000` | 8000 | 开发联调 |
| Vue 开发 | `cd frontend && npm run dev` | 5173 → proxy 8600 | 前端开发 |
| 生产 B/S | API + `frontend/dist` 静态挂载 | 8000 单端口 | 答辩推荐 |

麒麟注意：Vite 构建为静态文件，浏览器用系统 Chromium/Firefox；无需 Node 运行时上生产机。

---

## 9. 近期优先级（五层对齐）

| 优先级 | 任务 | 层 |
|--------|------|-----|
| P0 | [FIVE_LAYER_PIPELINE.md](FIVE_LAYER_PIPELINE.md) 文档落地 | 全层 |
| P0 | AgentChat 计划/执行双模式 + 批量队列 UI | 前端 L1/L3 |
| P1 | `/api/agent/plan` 与 `/api/agent/execute` 拆分 | L1/L3 |
| P1 | L1 并行编排器（边界+知识+静态感知） | L1 |
| P1 | MCP 工具四类分组 + 单一职责命名 | L3 |
| P1 | Gitee Wiki 只读同步 | L1/L4 |
| P2 | L4 知识回流 push Wiki | L4 |
| P2 | L5 analytics 模块 + 绘图 API | L5 |

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
| **[FIVE_LAYER_PIPELINE.md](FIVE_LAYER_PIPELINE.md)** | **五层流水线权威定义** |
| [MASTER_PLAN.md](MASTER_PLAN.md) | 总控计划、验收 |
| **本文** | 三交付线、模块矩阵、API |
| [TECH_STACK.md](TECH_STACK.md) | 依赖版本与自研模块清单 |
| [FINAL_ARCHITECTURE.md](FINAL_ARCHITECTURE.md) | 终版架构（替代旧 ARCHITECTURE.md） |
| [../A2_ARCHITECTURE_MAPPING.md](../A2_ARCHITECTURE_MAPPING.md) | 赛题得分点对照 |
| [../competitions/A2_OFFICIAL_GAP_ANALYSIS.md](../competitions/A2_OFFICIAL_GAP_ANALYSIS.md) | 官方缺口分析 |
| [../../frontend/package.json](../../frontend/package.json) | Vue 依赖锁定 |

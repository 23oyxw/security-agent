# 五层智能体流水线架构

> **终版权威（Agent 合并定义）** → **[FINAL_ARCHITECTURE.md](FINAL_ARCHITECTURE.md)** v0.8.0  
> **落地路线（定义封装→L5）** → **[ENCAPSULATION_TO_L5_ROADMAP.md](ENCAPSULATION_TO_L5_ROADMAP.md)**  
> **分级对照（建议 vs 实现）** → **[ARCHITECTURE_TIER_MAP.md](ARCHITECTURE_TIER_MAP.md)**  
> **版本**：v1.0 · **更新**：2026-06-11  
> 本文描述 **五层刚性流程** 细节；三代 Agent 合并关系以终版文档为准。

---

## 0. 核心设计原则

| 原则 | 说明 |
|------|------|
| **先分析、后防护、再执行、终审计迭代** | 强制流水线，禁止 skip |
| **L1/L2 禁止执行决策** | 工具调用仅 L3 execute 阶段（核心调度代理内） |
| **三代 Agent 固定** | core_dispatch · safety_sandbox · audit_iteration |
| **前端双模式** | 计划模式(L1) / 执行模式(L3) |
| **数据 Gitee Wiki** | 边界 · 检索 · 回流 |
| **工具单一职责** | 指标 / 日志 / 修复 / 调度 四簇 |
| **数学模型三场景** | 静态(L1) · 链路(L4) · 指标(L5) |
| **MCP 与流程一体** | MCP 原子工具 + L2 封装流程 **同一模块** 注册、热插拔、审计 |
| **单一工具单一职责** | 指标 / 日志 / 故障修复 / 资源调度 分工具，禁止「万能工具」 |
| **审计高要求** | 全链路 `trace_id`，L4 卷宗可导出、不可篡改（append-only） |
| **知识在 Gitee Wiki** | 边界对抗数据、规范知识库、知识回流案例 **统一存 Gitee Wiki**，本地索引可缓存 |

---

## 1. 前端：双模式 + 三代 Agent

> **完整论述** → [FINAL_ARCHITECTURE.md](FINAL_ARCHITECTURE.md) §一、§二、§三

### 1.1 计划 / 执行双模式 + 编排助手

```text
┌─────────────────────────────────────────────────────────────┐
│  AgentChat — 编排助手                                          │
│  [ 计划模式 L1 ] [ 执行模式 L3 ]                               │
│  三代：核心调度(L1+L3) · 安全沙箱(L2) · 审计迭代(L4+L5)        │
│  五层条：L1分析 → L2防护 → L3执行 → L4审计 → L5迭代            │
└─────────────────────────────────────────────────────────────┘
```

| 模式 | 触发 | 约束 |
|------|------|------|
| **计划** | L1 analyze | 零工具 · 零执行 |
| **执行** | L3 execute（同一 core_dispatch） | 需 L2 pass + plan_id |

### 1.2 批量指令

- 支持 **批量粘贴 / 多行指令队列**
- 每条指令独立 `trace_id`，共享同一 **分析计划批次号** `plan_batch_id`
- UI 状态机：`queued` → `analyzing` → `awaiting_approval` → `executing` → `audited`

---

## 2. 五层流水线总览

```text
用户输入（自然语言指令 / 预置流程 / 批量指令）
        │
        ▼
╔═══════════════════════════════════════════════════════════════╗
║ L1 感知与计划层（只读 · 不决策不执行）                          ║
║  ① 启动分析计划（Plan Agent · 与 L3 共用 Agent）               ║
║  ② 并行：                                                       ║
║     · 边界感知（对抗训练测规范边界）                             ║
║     · 知识库检索（分类清晰 · 支持回流扩充 · Gitee Wiki）         ║
║     · 静态感知「眼睛」：流量/端口/内存磁盘/组件/链路/权限/状态   ║
║  ③ 意图识别 → 输出结构化计划（无工具写操作）                     ║
╚═══════════════════════════════╤═══════════════════════════════╝
                                │ 计划就绪
                                ▼
╔═══════════════════════════════════════════════════════════════╗
║ L2 安全管控层（并排双轨 · 仍不决策执行）                        ║
║  ┌─────────────────────┐    ┌─────────────────────┐           ║
║  │ 安全控制             │    │ 沙箱                 │           ║
║  │ · 护栏 / 兜底        │    │ · 知识库检索         │           ║
║  │ · 超时 / 熔断        │    │ · 快捷流程试跑       │           ║
║  │ · MCP 热插拔         │    │ · 隔离环境验证       │           ║
║  │ · 高危命令截断       │    └─────────────────────┘           ║
║  │ · 清垃圾/内存需确认  │                                        ║
║  │ · CPU 告警弹窗       │                                        ║
║  └─────────────────────┘                                        ║
╚═══════════════════════════════╤═══════════════════════════════╝
                                │ verdict: pass | confirm | deny
                                ▼
╔═══════════════════════════════════════════════════════════════╗
║ L3 推理分发与执行层                                            ║
║  · 推理分发 Agent（与 L1 共用 · 执行模式）                     ║
║  · 调用 MCP 工具 或 封装流程（同一 mcp+flows 模块）            ║
║  · 工具域：指标 | 日志 | 故障修复 | 资源调度（单一职责）        ║
╚═══════════════════════════════╤═══════════════════════════════╝
                                │
                                ▼
╔═══════════════════════════════════════════════════════════════╗
║ L4 审计与知识回流层                                            ║
║  · 审计日志分析（高要求 · append-only · trace_id）             ║
║  · 链路追溯（六阶段 Trace · 卷宗导出）                         ║
║  · 知识回流：安全案例解析 → 打标签 → 写入 Gitee Wiki           ║
╚═══════════════════════════════╤═══════════════════════════════╝
                                │
                                ▼
╔═══════════════════════════════════════════════════════════════╗
║ L5 数学模型分析层                                              ║
║  · Agent：准确率 / 召回率 / F1 / 延迟分布                      ║
║  · 静态感知：时序绘图（CPU/内存/端口/链路）                    ║
║  · 链路日志：Trace 阶段耗时、异常归因可视化                    ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## 3. 各层详细规格

### L1 — 三感知 analyze 阶段（核心调度代理 · 阶段 A）

**三感知并行**，意图识别紧随其后；**禁止** MCP / executor 写操作。

| 感知 | 说明 | 模块 |
|------|------|------|
| **① 抗性边界感知** | 对抗训练 + **权限跃迁阻力**对抗训练 · 越界识别 | `l1_triple_perception.run_adversarial_boundary_perception` |
| **② 灵敏知识库检索** | 规范/流程/故障/调度/工具 · 高灵敏检索 | `run_sensitive_knowledge_retrieval` |
| **③ 静态环境感知（眼）** | 网络/端口/CPU/内存/磁盘/链路/权限/状态 | `run_static_environment_eye` |

```text
用户指令
    ├── parallel ──► ① 抗性边界感知   → boundary_hits + 跃迁探针 → Wiki
    ├── parallel ──► ② 灵敏知识检索   → knowledge_refs           → Wiki
    └── parallel ──► ③ 静态环境（眼）  → static_snapshot          → Wiki
                              │
                              ▼
                      意图识别 → plan 结构体（phase_lock=L1_only）
```

**L1 输出契约**（`AnalysisPlan` + `triple_perception`）：

```json
{
  "plan_id": "uuid",
  "trace_id": "uuid",
  "intent": "cleanup_disk",
  "steps": [{"phase": "感知", "readonly": true}, {"phase": "执行", "tools": ["..."]}],
  "boundary_hits": [],
  "knowledge_refs": ["wiki://规范/磁盘清理"],
  "static_snapshot_id": "snap-xxx",
  "requires_confirm": true
}
```

---

### L2 — 安全管控层

**职责**：安全评估与隔离试跑。**仍不触发** L3 写执行。

| 轨道 | 能力 | 说明 |
|------|------|------|
| **安全控制** | 护栏 | `ThreeLayerDefenseEngine` L1/L2/L3 加权 |
| | 兜底 | `resilience/degradation.py` S0–S2 |
| | 超时熔断 | `resilience/budget.py` · `resilience/circuit.py` |
| | MCP 热插拔 | `mcp/registry.py` · `POST /api/mcp/reload` |
| | 高危截断 | `rules/engine` → `DENY` 直接截断 |
| | 清垃圾/释内存 | `NEED_CONFIRM` 强制人工确认 |
| | CPU 告警弹窗 | `monitor/` → 前端 `Alerts` / 桌面通知 |
| **沙箱（并排）** | 知识检索 | 沙箱内只读查 Wiki 片段 |
| | 快捷流程 | `skills/flows/` 在沙箱内 dry-run |
| | 隔离验证 | `terminal/sandbox.py` 无真实写 |

**L2 输出**：`SafetyVerdict` = `pass` | `confirm` | `deny` | `quarantine`

---

### L3 — 推理分发与执行层

**职责**：在 L2 通过后，由 **同一 Agent（执行模式）** 推理并分发。

| 项 | 说明 |
|----|------|
| Agent | 与 L1 **共用** `AgentBrain` / `Orchestrator`，通过 `mode=plan|execute` 切换 |
| MCP + 流程 | **统一模块** `mcp/` + `skills/flows/` + `tools/registry` |
| 工具分类 | 见 §4 |
| 执行路径 | `orchestrator.dispatch` → `SafetyGate`（二次）→ `executor` / MCP |

---

### L4 — 审计与知识回流层

| 项 | 要求 |
|----|------|
| 审计日志 | append-only JSONL · 字段完整 · 敏感脱敏 · **高可靠** |
| 链路追溯 | 全链路 `trace_id` · 六阶段 · `GET /api/trace/{id}/export` |
| 知识回流 | 安全案例解析 → 结构化标签 → **写入 Gitee Wiki** → 更新本地索引 |

**回流标签体系**（示例）：

`threat:` · `tool:` · `verdict:` · `os:` · `severity:` · `reflex:`

---

### L5 — 数学模型分析层

> **完整方案** → [L5_ANALYTICS.md](L5_ANALYTICS.md)

| 用途 | 指标 / 输出 | 实现 |
|------|-------------|------|
| **散点离群** | 单 trace 耗时×错误率×抖动；3σ + IQR | `l5/analytics.py` · `/api/l5/scatter` |
| **热力矩阵** | 时间×服务接口加权密度 | `/api/l5/heatmap` |
| **链路溯源** | Span 瀑布 · 根因候选 | `/api/l5/root-cause/{id}` |
| **六维量化** | 意图/边界/修复/调度/批量/工具 | `/api/eval/score` + `l5-metrics.js` |
| **集成测试** | L1–L5 模块链路矩阵 | `/api/l5/integration/*` |

前端专属页：**`/l5`**（`L5Analytics.vue`）· 运维概览 **`/`** 与之分离。

模块：`security_agent/l5/` · 前端 ECharts 5

---

## 4. MCP 工具与封装流程（L3 统一模块）

### 4.1 工具域与单一职责

| 域 | 职责 | 示例工具（目标命名） |
|----|------|----------------------|
| **指标 metrics** | 采集与聚合性能指标 | `metric_cpu_snapshot` · `metric_disk_usage` · `metric_load_avg` |
| **日志 logs** | 检索、模式匹配、增量扫描 | `log_tail` · `log_pattern_scan` · `log_error_rate` |
| **故障修复 repair** | 诊断与受控修复（经 L2） | `repair_clean_tmp` · `repair_restart_service` · `repair_rollback_config` |
| **资源调度 schedule** | 进程/服务/配额调度建议与执行 | `sched_kill_zombie` · `sched_nice_process` · `sched_disk_quota_check` |

**规则**：一个工具只做一件事；复合场景走 **封装流程**（L2 flow），不在单工具内堆逻辑。

### 4.2 MCP + Flow 一体注册

```text
mcp_module/
  ├── registry.py          # 热插拔、manifest
  ├── tools/               # L1 原子 MCP 工具
  └── flows/               # L2 封装流程（与 skills/flows 合并视图）
```

REST：`GET /api/mcp/servers` · `POST /api/mcp/reload` · `POST /api/skills/flows/{name}/run`

---

## 5. 知识库与 Gitee Wiki

| 数据类型 | 存储 | 用途 |
|----------|------|------|
| **规范知识库** | Gitee Wiki | L1 检索 · 分类：规范/剧本/工具文档 |
| **边界对抗数据** | Gitee Wiki | L1 边界感知 · 对抗样本与期望 verdict |
| **知识回流案例** | Gitee Wiki | L4 写入 · 带标签的安全案例 |
| **本地索引** | `data/knowledge_index/` | 缓存 + 增量同步 Wiki |

同步策略：启动拉取 · 回流 push · Webhook 可选（P2）

---

## 6. 与 A2 五大支柱对照

| 赛题支柱 | 主要落入层 | 说明 |
|----------|------------|------|
| ① OS 深度感知 | **L1** 静态感知 | 眼睛只读；L5 绘图 |
| ② MCP 插件化 | **L3** 执行 | 与 flows 一体；L2 热插拔 |
| ③ 安全意图校验 | **L2** 安全控制 | 护栏/熔断/确认 |
| ④ 最小权限执行 | **L2 沙箱** + **L3** | 沙箱试跑 → 正式 executor |
| ⑤ 推理链路溯源 | **L4** | trace_id + 卷宗 + 回流 |

---

## 7. API 路由规划（目标）

| 层 | 方法 | 路径 | 说明 |
|----|------|------|------|
| L1 | POST | `/api/agent/plan` | 分析计划（只读） |
| L1 | POST | `/api/perception/static` | 静态感知快照 |
| L1 | POST | `/api/knowledge/search` | Wiki 检索 |
| L1 | POST | `/api/boundary/evaluate` | 边界对抗测试 |
| L2 | POST | `/api/safety/defense/evaluate` | 三层防御 |
| L2 | POST | `/api/sandbox/dry-run` | 沙箱试跑 |
| L3 | POST | `/api/agent/execute` | 推理分发执行 |
| L3 | POST | `/api/skills/flows/{name}/run` | 封装流程 |
| L4 | GET | `/api/trace/{id}` | 链路追溯 |
| L4 | POST | `/api/knowledge/reflux` | 知识回流 → Wiki |
| L5 | GET | `/api/l5/scatter` | 散点 + 3σ/IQR |
| L5 | GET | `/api/l5/heatmap` | 热力矩阵 |
| L5 | GET | `/api/l5/root-cause/{trace_id}` | 链路根因 |
| L5 | POST | `/api/l5/integration/run` | 模块链路集成测试 |
| L5 | GET | `/api/eval/score` | 六维量化指标 |

**现有** `/api/agent/chat` 演进为：`mode=plan` → L1 路径；`mode=execute` + `plan_id` → L3 路径。

---

## 8. 实现状态矩阵（2026-06-11）

| 能力 | 层 | 状态 |
|------|-----|------|
| 分析计划 Agent | L1/L3 共用 | ⚠️ 需显式 plan/execute 模式 |
| 边界感知对抗 | L1 | ⚠️ demo/boundary 有；Wiki 同步 ❌ |
| 知识库 Wiki 回流 | L1/L4 | ⚠️ 本地 playbook 有；Gitee Wiki ❌ |
| 静态感知并行 | L1 | ⚠️ monitor/scanner 有；未统一 L1 编排 |
| L1/L2 执行闸门 | L1/L2 | ⚠️ 部分；需 API 层强制 |
| 安全控制全套 | L2 | ✅ 三层防御/熔断/确认 |
| 沙箱并排 | L2 | ✅ sandbox；dry-run API ⚠️ |
| MCP+Flow 一体 | L3 | ⚠️ 模块分散，文档已统一 |
| 工具四类拆分 | L3 | ⚠️ 需重构命名与 registry 分组 |
| 审计高要求 | L4 | ✅ trace/spine；回流 Wiki ❌ |
| 数学模型 L5 | L5 | ❌ analytics 模块待建 |
| 前端计划/执行双模式 | UI | ❌ AgentChat 待改 |
| 批量先分析后执行 | UI | ❌ 待建 |

---

## 9. 迁移路线（P0 → P2）

| 阶段 | 任务 |
|------|------|
| **P0** | 文档对齐（本文）· AgentChat 计划/执行 Tab · `/api/agent/plan` 草案 |
| **P1** | L1 并行编排器 · L2 执行闸门 middleware · Gitee Wiki 只读同步 |
| **P1** | MCP 工具按 metrics/logs/repair/schedule 分组注册 |
| **P2** | L4 知识回流 push Wiki · L5 analytics 模块 · 批量指令队列 UI |
| **P2** | 数学模型驱动 Dashboard / Trace 增强图表 |

---

## 10. 文档索引

| 文档 | 内容 |
|------|------|
| **本文** | 五层流水线权威定义 |
| [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) | 三交付线 + 模块矩阵（已对齐五层） |
| [MASTER_PLAN.md](MASTER_PLAN.md) | 总控计划与验收（已对齐五层） |
| [../../frontend/ARCHITECTURE.md](../../frontend/ARCHITECTURE.md) | 前端计划/执行模式与 API |
| [../A2_ARCHITECTURE_MAPPING.md](../A2_ARCHITECTURE_MAPPING.md) | 赛题得分点 ↔ 五层映射 |

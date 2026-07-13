# 人工智能安全运维智能体 — 最终架构完整论述

> **版本**：v0.9.0 · **更新**：2026-07-13  
> **地位**：技术重构 **唯一权威** 文档。其余架构文档均须与本篇对齐，冲突以本文为准。  
> **记忆公式**：**1 调度 + 1 安全 + 1 迭代** · 前析后防再执行，审计绘图自更新 · 数据全部进 Wiki，工具单一职责化 · 批量必须先分析，全程追踪可溯源  
> **v0.9.0 升级**：6 步全域升级已完成 — 沙箱透明化 · 告警安静化 · 终端智能化 · 文档活化 · 边界自检化 · 知识自愈化

---

## 一、整体架构设计思想

本智能体采用 **前端双模式 + 五层刚性流程 + 三智能体协同** 体系。

整体遵循 **先分析、后防护、再执行、终审计迭代** 的强制流水线，**绝不允许**任何指令跳过前置分析直接执行。

| 维度 | 设计 |
|------|------|
| 前端 | **计划模式 / 执行模式** 双模式切换；单条 + 批量指令 |
| 流程 | 五层刚性流水线，层间闸门不可 bypass |
| 智能体 | **3 个永久固定** Agent（见第二节） |
| 数据 | 全闭环托管 **Gitee Wiki**（边界对抗 / 检索 / 回流） |
| 工具 | **单一工具、单一职责**；四大场景簇 |
| 数学模型 | 静态绘图(L1) · 链路绘图(L4) · 全量指标迭代(L5) |

---

## 二、三代（Agent）体系 — 重构核心主体

```text
                    ┌─────────────────────────────────────┐
                    │  前端：计划模式 │ 执行模式 + 批量队列   │
                    └──────────────────┬──────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ ① 核心调度代理   │         │ ② 安全防护沙箱   │         │ ③ 审计迭代代理   │
│ L1 + L3 合并    │ ──gate──│ L2 独立         │ ──gate──│ L4 + L5 合并    │
│ 阶段锁 analyze  │         │ 零执行零决策     │         │ 溯源·绘图·回流   │
│      execute    │         │                 │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

### 2.1 核心调度代理 `core_dispatch`（L1 + L3 合并）

**本次架构最重要的合并**：前置分析计划与推理分发执行属于同一业务流上下游，合并为 **同一 Agent**，保证上下文不丢失、分析结果无缝对接执行决策。

| 阶段 | 层级 | 能力 | 硬性约束 |
|------|------|------|----------|
| **阶段 A：analyze** | L1 | **三感知并行**（见下）+ 数学模型静态绘图 + Wiki 落库 | **只分析、不决策、不执行、不调用任何 MCP/工具** |

#### L1 三感知（并行 · 核心约束：零工具零执行）

| # | 模块 | 能力 | 数据落库 |
|---|------|------|----------|
| ① | **抗性边界感知** | 对抗训练边界校验 · **权限跃迁阻力**对抗训练 · 越界识别 | Gitee Wiki 对抗集 |
| ② | **灵敏知识库检索** | 规范/流程/故障/调度/工具说明 · 高灵敏 hybrid 检索 | Gitee Wiki 知识索引 |
| ③ | **静态环境感知（眼）** | 网络·端口·CPU·内存·磁盘·链路·权限·系统状态 | Gitee Wiki 感知快照 |

**实现**：`security_agent/agent/l1_triple_perception.py` · `run_triple_perception_parallel()`
| **阶段 B：execute** | L3 | L2 通过后开启；推理决策；调度 MCP + 封装流程；单/批量编排 | **唯一允许工具调用与写操作的阶段**（在本 Agent 内） |

**阶段锁机制**：`phase=analyze` 时禁止进入 execute；必须持有 `plan_id` + L2 verdict ≠ deny 方可 `phase=execute`。

**工具体系（单工具单职责 · 四大簇）**

| 簇 | 职责示例 | 模块映射（目标） |
|----|----------|------------------|
| **指标采集** | CPU/内存/磁盘/网络/任务成功率 | `get_system_health`, metrics MCP |
| **日志处理** | 抓取、trace 解析、错误分类、批量结构化 | journal/syslog 工具 |
| **故障修复** | 端口/进程/权限/清理/链路自愈 | repair flows, terminal (gated) |
| **资源调度** | 算力/内存/磁盘配额/优先级/批量预调度 | schedule flows |

**代码映射**：`security_agent/agent/core_agents.py` · `agent_plan.py` · `brain.chat(plan=…)` · `tools/registry`

---

### 2.2 安全防护沙箱代理 `safety_sandbox`（L2 独立）

第二层 **完全独立**，不参与分析、不参与执行、不参与决策。

| 能力 | 说明 |
|------|------|
| 意图识别（安全维度） | 与 L1 业务意图互补，专注风险分类 |
| 全局护栏 | 超时熔断 · MCP 热插拔 · 高危命令截断 · 二次确认 · CPU/资源弹窗 |
| 沙箱隔离 | 独立 KB 检索 · 批量预演 · 风险模拟 |

**硬性规则**：L2 全程 **零执行、零决策、零工具调用** — 只拦截、只校验、只防护。系统 **唯一安全闸门**。

**代码映射**：`run_l2_precheck` · `ThreeLayerDefenseEngine` · `SafetyGate`

---

### 2.3 审计溯源 & 数学模型迭代代理 `audit_iteration`（L4 + L5 合并）

后置闭环 **唯一代理**：收尾、可视化、审计、知识沉淀、模型迭代。

| 阶段 | 层级 | 能力 |
|------|------|------|
| **审计溯源** | L4 | 全局 `trace_id`；append-only 审计卷宗；链路时序/拓扑/异常分布 **绘图**；案例解析 → 打标签 → **Gitee Wiki 回流** |
| **量化迭代** | L5 | 散点(3σ/IQR) · 热力(加权密度) · Span 溯源 · 六维指标 · 模块集成测试 → **反向优化**规则/权重/阈值 |

详见 [L5_ANALYTICS.md](L5_ANALYTICS.md) · 前端 `/l5`

**代码映射**：`audit/spine` · `TraceView` · `eval/` · Wiki reflux API（待建）

---

## 三、五层刚性运行流水线（终版）

```text
用户输入（单条 / 批量）
        │
        ▼
┌─ 前端层 ────────────────────────────────────────────────┐
│ 计划模式：触发 L1 analyze，禁用 execute                    │
│ 执行模式：展示 L3 进度，需 plan_id + L2 pass               │
│ 批量：每条独立 trace，共享 batch_id，强制全流程             │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌─ L1 核心调度代理 · analyze 阶段 ─────────────────────────┐
│ 并行：边界感知 ∥ 知识检索 ∥ 静态感知                        │
│ 数学模型：静态状态/资源/拓扑绘图                            │
│ Wiki：对抗数据 + 检索记录 + 感知快照结构化入库              │
│ 约束：零工具 · 零执行 · 零决策                              │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌─ L2 安全防护沙箱代理 ────────────────────────────────────┐
│ 意图(安全) · 护栏 · 沙箱预演 · verdict: pass|confirm|deny  │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌─ L3 核心调度代理 · execute 阶段 ─────────────────────────┐
│ 推理分发 · MCP/Flow · 四大工具簇 · 单/批量编排              │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌─ L4 审计迭代代理 ────────────────────────────────────────┐
│ 不可篡改审计 · trace 卷宗 · 链路日志绘图 · Wiki 知识回流    │
└───────────────────────────┬───────────────────────────────┘
                            ▼
┌─ L5 审计迭代代理 ────────────────────────────────────────┐
│ 全维度指标量化 · 性能复盘 · 策略自进化                      │
└───────────────────────────────────────────────────────────┘
```

---

## 四、硬性架构约束（重构必守）

1. **Agent 结构**：3 个永久固定 — `core_dispatch` · `safety_sandbox` · `audit_iteration`
2. **L1/L2 禁止执行决策**：任何工具、任务、流程 **仅 L3 execute 阶段**
3. **工具单一职责**：禁止多功能耦合工具
4. **核心数据统一 Gitee Wiki**：边界对抗 · 检索 · 回流
5. **数学模型三场景固定**：静态绘图(L1) · 链路绘图(L4) · 指标迭代(L5)
6. **批量强制前置全流程**：不允许批量直执行
7. **审计 append-only + 全链路 trace**

---

## 五、API 与前端映射（实现 v1.0）

| 前端模式 | API | Agent 阶段 |
|----------|-----|------------|
| 计划模式 | `POST /api/agent/plan` 或 `orchestrate`（无 auto_execute） | L1 analyze |
| 执行模式 | `POST /api/agent/execute` | L3 execute（同一 core_dispatch） |
| L2 | `POST /api/agent/l2/precheck` | safety_sandbox |
| 收尾 | 执行后自动 | audit_iteration.finalize |
| 主编排 | `POST /api/agent/orchestrate` | 全链 |

| 前端组件 | 职责 |
|----------|------|
| `OrchestratorPipeline` | 三 Agent 状态 + 五层标签 |
| `PlanPanel` | L1 analyze 产物 |
| `ExecutePanel` | L3 execute 产物 |
| `AuditPanel` | L4/L5 审计与指标摘要 |
| `PersonaCoordPanel` | 用户/运维/开发角色提示 + ID 实体 |
| 计划/执行 Segmented | 双模式切换 |

---

## 六、实现状态矩阵

| 能力 | 状态 |
|------|------|
| core_dispatch analyze/execute 阶段锁 | ✅ |
| safety_sandbox L2 预检 | ✅ |
| audit_iteration finalize 桩 | ✅ trace/指标/Wiki 回流 |
| 前端双模式 + 三 Agent 流水线 | ✅ |
| 四大工具簇注册分组 | ✅ registry + cluster_map |
| 计划持久化 plans.db | ✅ |
| trace_id 全链路归一 | ✅ |
| 多角色协调文档 | ✅ MULTI_PERSONA_COORDINATION.md |
| PersonaCoordPanel | ✅ AgentChat 侧栏 |
| 全域沙箱 7 层隔离 | ✅ sandbox/ (v0.9) |
| 告警 5 层降噪 | ✅ notify/ (v0.9) |
| 终端 5 阶段智能闭环 | ✅ terminal/ (v0.9) |
| 文档智能 Pipeline | ✅ document/ (v0.9) |
| 边界 12 探针 + Fuzzer | ✅ sandbox/probes.py + fuzzer.py (v0.9) |
| 知识自愈（一致性+新鲜度） | ✅ knowledge/guard.py + freshness.py (v0.9) |
| 能力装箱（CapabilityRegistry） | ✅ capability/ (v0.9) |
| Gitee Wiki 全量落库 | ⚠️ 本地知识库完整，Wiki push 待建 |
| L1/L5 数学绘图 API | ✅ L5 `/api/l5/*` · L1 静态在 perception |
| L5 专属页 `/l5` | ✅ 散点/热力/溯源/集成测试 |
| 侧栏 autorun 跑到底 | ✅ GATE/L3 → L3/L4 → `/l5` |

## 六-B、v0.9.0 模块清单（实际）

```
security_agent/        260 py · 23 test files
├── agent/             25py   Brain · Orchestrator · Fallback · L1_TriplePerception
│                             · Autonomous · Evaluation · ReactContext · CoreAgents
├── analysis/           2py   任务分析器
├── api/               34py   FastAPI + 路由(17) + WS + MCP_Host
├── audit/              9py   IncidentSpine · Trace · 六阶段
├── auth/               5py   JWT · RBAC · Models · Store
├── capability/         5py   🆕 Registry · Guard · ToolBox · FlowBox · PluginBox
├── confirm/            2py   S4 审批队列
├── contracts/          2py   三方契约加载器
├── demo/               7py   竞赛演练场景
├── document/           8py   🆕 Pipeline · Chunker · Embedder · Indexer · Parsers(2)
├── filesystem/         3py   🆕 VersionManager · SafeOps
├── inspection/         5py   华测式巡检引擎
├── knowledge/         14py   Playbooks(30+) · GiteeWiki(7) · Guard · Freshness
├── l5/                 8py   数学模型 · Analytics · PolicyFeedback
├── mcp/                3py   统一MCP注册中心
├── memory/             3py   对话记忆 + 语义记忆
├── monitor/            8py   巡检 + 动态阈值
├── notify/             6py   🆕 告警 + 节流 + 浮屏
├── ops/                3py   守卫 + 任务分发
├── pipeline/           8py   五层流水线引擎
├── resilience/         4py   预算·熔断·降级 S0-S4
├── retrieval/          4py   混合检索
├── rules/              2py   规则引擎
├── safety_gate/        9py   三层防御 · 快照 · 注入 · MAC检查
├── sandbox/            7py   🆕 Profile · OverlayFS · Namespace · Session · Probes · Fuzzer
├── scanner/            2py   安全扫描
├── security/           3py   脱敏
├── skills/            41py   17 Skills + 6 Flows
├── storage/            5py   快照+Trace 持久化
├── terminal/           8py   🆕 Executor · Context · PreAnalyzer · PostVerifier · Learner
├── tools/              5py   工具注册中心 + 四大簇
├── utils/              2py   Token管理
├── visualizer/         2py   Trace可视化
└── workflow/           2py   状态机引擎

tests/                 23 files · 137+ test cases
```

---

## 七、设计原则（v0.9 新增）

> 来源：[EXPERIENCE_DRIVEN_DESIGN.md](EXPERIENCE_DRIVEN_DESIGN.md) — 从用户体感倒推架构决策

| # | 原则 | 架构决策 |
|---|------|----------|
| 1 | **不打扰** — 能自动处理的绝不告警，能告警的绝不中断 | 告警系统五层降噪（频率节流→去重→衍生抑制→关联→分级） |
| 2 | **可解释** — 每个决策都要能回答「为什么」 | 三层防御评分分解到 L1/L2/L3 子项；终端操作附带风险因子说明 |
| 3 | **可追溯** — 任何操作都有前→中→后快照 | 全域沙箱 OverlayFS 写时复制 + FileChangeReport；trace_id 贯穿 |
| 4 | **渐进式** — 新用户 5 分钟上手，老用户能深挖 | 前端双模式（计划/执行）→ 一键操作 → 高级编排 |
| 5 | **自愈优先** — 先尝试自动修复，实在不行再找人 | 告警附带的 recommended_action 自动执行；磁盘清理/进程重启优先静默处理 |

## 八、v0.9.0 演进（✅ 已完成）

| 方向 | 当前级别 | v0.9 目标 | 状态 |
|------|----------|-----------|------|
| 全域沙箱 | 演示级（setuid+rlimit） | 7 层隔离（OverlayFS+namespace） | ✅ |
| 告警降噪 | 中等级（去重+衍生抑制） | 五层降噪（频率节流+浮屏控制） | ✅ |
| 终端智能 | 基础级（无状态执行） | 五阶段闭环（上下文→预分析→验证→学习） | ✅ |
| 文档智能 | 不存在 | Pipeline（解析→分块→索引→检索→自抽取） | ✅ |
| 边界韧性 | 基础级（权限探针） | 12 探针网格 + 7 策略 Fuzzer | ✅ |
| 知识自愈 | 基础级（30条硬编码） | 一致性校验 + 防污染 + 新鲜度追踪 | ✅ |
| 能力装箱 | 5 入口散落 | CapabilityRegistry 单入口 + Guard 自动保护 | ✅ |

6 步实施路线详见 [MASTER_PLAN.md §11](MASTER_PLAN.md)。

## 九、架构优势摘要

1. 主体分工清晰：**感知执行一体（阶段锁）· 安全独立 · 审计迭代独立**
2. 安全等级高：双层前置 + 沙箱 + 事后审计
3. 工具生态解耦：单职责便于迭代
4. 数据闭环：Wiki 永久沉淀
5. 可视化全覆盖：静态 + 链路双绘图
6. 自进化：L5 量化复盘反写策略

---

## 关联文档

| 文档 | 关系 |
|------|------|
| [FIVE_LAYER_PIPELINE.md](FIVE_LAYER_PIPELINE.md) | 五层细节补充（服从本文 Agent 合并定义） |
| [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) | 模块矩阵与交付线 |
| [EXPERIENCE_DRIVEN_DESIGN.md](EXPERIENCE_DRIVEN_DESIGN.md) | 🆕 体验驱动设计 — 从用户体感倒推接口契约（本文 §七的设计原则来源） |
| [FULL_DOMAIN_UPGRADE.md](FULL_DOMAIN_UPGRADE.md) | 🆕 生产级技术方案 — 7 模块升级的技术细节（本文 §八的实现方案） |
| [MASTER_PLAN.md](MASTER_PLAN.md) | 总控计划 — 含 v0.9 升级 6 步路线（本文 §八的执行计划） |
| [../../frontend/ARCHITECTURE.md](../../frontend/ARCHITECTURE.md) | 前端双模式与组件 |
| [ORCHESTRATOR_THREE_AGENTS.md](ORCHESTRATOR_THREE_AGENTS.md) | 已归并至本文 §二、§五 |

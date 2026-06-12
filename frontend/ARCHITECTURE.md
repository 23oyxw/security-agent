# Vue3 前端架构 v1.0-final

> **终版权威**：[docs/architecture/FINAL_ARCHITECTURE.md](../docs/architecture/FINAL_ARCHITECTURE.md)  
> **侧栏规范**：[docs/architecture/FRONTEND_SIDEBAR.md](../docs/architecture/FRONTEND_SIDEBAR.md)  
> **L5 链路分析**：[docs/architecture/L5_ANALYTICS.md](../docs/architecture/L5_ANALYTICS.md)  
> **多角色协调**：[docs/architecture/MULTI_PERSONA_COORDINATION.md](../docs/architecture/MULTI_PERSONA_COORDINATION.md)

## 设计公式

**1调度 + 1安全 + 1迭代** · 前端 **计划/执行双模式** · 五层刚性流程

## 单一数据源

| 模块 | 路径 | 职责 |
|------|------|------|
| 页面编排 | `constants/navigation.js` | 页 meta · 面包屑 · 底部链接 |
| 侧栏五层 | `constants/pipeline-architecture.js` | 层卡片 · 主按钮 · extras |
| 三 Agent 视觉 | `constants/agent-visual.js` | 色带 · 括号 · 状态灯 |
| L5 指标 | `constants/l5-metrics.js` | 六维量化 · 自进化建议 |
| 画布拓扑 | `constants/canvas-topology.js` | L1–L5 架构画布节点 |
| 流水线动作 | `constants/actions.js` | PipelineBtn |
| Agent 元数据 | `constants/agents.js` | 三 Agent · 工具簇 |

## 布局

```text
MainLayout
├── Sidebar（可拖宽 300–520px）
│   ├── PipelineArchitectureRail（五层 + 三 Agent 色带 + 状态灯）
│   └── 底部：导引 / 用户管理
├── Topbar
└── router-view
```

## 页面映射

| 路径 | 名称 | 层 | Agent |
|------|------|-----|-------|
| `/agent` | 智能体对话 | L1+L3 | core_dispatch |
| `/safety` | L2 防护沙箱 | L2 | safety_sandbox |
| `/alerts` | 告警（L2 extra） | L2 | — |
| `/mcp` | 工具中心（L3 extra） | L3 | — |
| `/trace` | L4 审计 | L4 | audit_iteration |
| **`/l5`** | **L5 链路分析** | L5 | audit_iteration |
| `/` | 运维概览 | — | — |
| `/canvas` | 五层架构画布（L5 extra） | L1–L5 | — |
| `/guide` | 架构导引 | — | — |
| `/knowledge` | 知识库（L1 extra） | L1 | — |

## `/agent` 工作流

```text
计划/执行 Segmented + 对话区
侧栏 GATE/L3 → autorun 自动 L3→L4→跳转 /l5
抽屉：OrchestratorPipeline · PlanPanel · ExecutePanel · AuditPanel
```

## API 与模式

| 模式 | 行为 |
|------|------|
| 计划 | `orchestrate` 无 auto_execute |
| 执行 | `execute`（需 plan + L2 pass）→ 可选自动跳转 `/l5` |

L5 专用 API：`/api/l5/scatter` · `/heatmap` · `/root-cause/{id}` · `/integration/*`

详见终版文档 §五 · [L5_ANALYTICS.md](../docs/architecture/L5_ANALYTICS.md)

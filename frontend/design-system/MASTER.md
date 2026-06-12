# Security Agent — Design System v1.0-final

> [FINAL_ARCHITECTURE.md](../docs/architecture/FINAL_ARCHITECTURE.md)

## 公式

**1调度 + 1安全 + 1迭代** · 计划/执行双模式 · 五层刚性流程

## 页面编排（navigation.js）

全站侧栏、面包屑、PillarRail、PageHeader 标题 **必须** 引用 `constants/navigation.js`，禁止各页硬编码名称。

## 按钮语义（PipelineBtn + actions.js）

| 层 | type | 典型 action |
|----|------|-------------|
| L1 | primary | `l1Analyze` · `batchEnqueue` |
| L2 | warning | `l2Precheck` |
| L3 | success | `l3Execute` |
| L3 确认 | warning | `l3ConfirmExecute` |
| L4 | info plain | `traceView` |
| 中性 | default plain | `clear` · `refresh` |

## 三代 Agent 视觉

| Agent | 色 | 图标 |
|-------|-----|------|
| core_dispatch | primary | Cpu |
| safety_sandbox | warning | Lock |
| audit_iteration | info | DataLine |

## 面板边框语义

| 组件 | 层 | 边框 |
|------|-----|------|
| PlanPanel | L1 analyze | info/warning 三感知卡 |
| ExecutePanel | L3 execute | success |
| AuditPanel | L4+L5 | neutral/info |

## 反模式

- 跳过 L1 直执行
- L1/L2 页面提供「执行工具」主按钮
- 各页自定义不一致的 L1/L2/L3 命名
- 绕过 PipelineBtn 散落 el-button type 语义

# 前端侧栏架构说明

> **权威**： [FINAL_ARCHITECTURE.md](./FINAL_ARCHITECTURE.md) · **实现**： `PipelineArchitectureRail.vue`

## 设计原则

1. **单一导航入口** — 侧栏顶部旧分组菜单（智能体/总览/安全/流水线/知识）已移除，避免与五层流程按钮重复占宽。
2. **五层 = 主按钮** — 每层一张卡片 + 一个 `RailActionBtn` 主操作，对应架构刚性流程。
3. **三 Agent = 色带 + 括号** — 不破坏 L1→L5 顺序，用颜色与括号标注归属：
   - 蓝 `#3b82f6` · **核心调度**（L1、层间门禁、L3）
   - 绿 `#10b981` · **安全沙箱**（L2）
   - 紫 `#8b5cf6` · **审计迭代**（L4、L5）
4. **主线状态灯** — 侧栏左侧竖线 + 圆点，与 L1/L2/GATE/L3/L4/L5 对齐；`running` 脉冲 / `done` 实心 / `blocked` 红。
5. **层内辅助链接** — 知识库、告警、MCP、画布等作为 **extras**，挂在对应层卡片下，不是第二套顶栏菜单。

## 宽度

- 默认 **360px**，可拖动右缘手柄调整（**300–520px**），写入 `localStorage: security-agent-sidebar-width`。
- 折叠宽度不变（`--sidebar-collapsed-width`）。

## 页面映射（主按钮）

| 层 | 主按钮 | 路由 |
|----|--------|------|
| L1 | 计划模式对话 | `/agent`（plan） |
| L2 | L2 防护沙箱 | `/safety` |
| GATE | 切换执行模式 | `/agent`（autorun → L3/L4/L5） |
| L3 | 执行模式对话 | `/agent`（execute） |
| L4 | Trace 卷宗 · 审计追溯 | `/trace` |
| L5 | 链路量化分析 · 统计迭代 | `/l5` |

## 层内 extras

| 层 | 辅助入口 |
|----|----------|
| L1 | `/knowledge` |
| L2 | `/alerts`（带未读 badge） |
| L3 | `/mcp` |
| L5 | `/canvas` |

## 底部

- 架构导引 `/guide`
- 用户管理 `/users`（admin）

## 顶栏

- 已移除 `PillarWorkflowRail`（与侧栏重复）。
- 面包屑 + 「智能体对话」快捷入口保留。

## 认证与误登出

- Axios **仅在 `/auth/*` 返回 401 时登出**；业务 API 401/403 不自动踢出（Mock token 打真实后端时常见）。
- 开发请使用 `VITE_MOCK=true` 或确保后端接受当前 token。

## 相关文件

| 文件 | 职责 |
|------|------|
| `constants/pipeline-architecture.js` | 五层文案、主 action、extras |
| `constants/agent-visual.js` | 三 Agent 色值与括号 |
| `constants/navigation.js` | 页 meta、底部链接（无分组菜单） |
| `constants/l5-metrics.js` | L5 六维指标 |
| `views/L5Analytics.vue` | L5 专属页 `/l5` |
| `components/layout/PipelineArchitectureRail.vue` | 侧栏主体 UI |

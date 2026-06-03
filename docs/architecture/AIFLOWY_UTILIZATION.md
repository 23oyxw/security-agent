# AIFlowy 利用价值评估

> **对象**：仓库内 `aiflowy-main/`（开源 AI 应用平台 v2.1.x）  
> **对照**：[MASTER_PLAN.md](MASTER_PLAN.md) · [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)  
> **结论**：**中等参考价值，不建议并入主干部署**；与 Dify/qt01 同属「第四条参考线」。

---

## 1. AIFlowy 是什么

| 维度 | 说明 |
|------|------|
| 定位 | 开源 AI 应用开发与运营平台（Bot + RAG + Workflow + MCP + 模型管理） |
| 技术栈 | Java Spring Boot + MySQL + Redis + Vue 管理端/用户中心 |
| 部署 | `docker-compose` 需 API(:8080) + Admin(:8081) + UserCenter(:8082) + MySQL + Redis |
| 工作流 | 基于 **tinyflow** 可视化编排，支持 JSON 导入、自定义节点 |
| MCP | 内置 MCP 管理、挂载到 Bot、工具调用展示 |
| RAG | 知识库、向量库、多检索器（ES/Lucene 等） |

与赛题主干 **Python FastAPI + 三层防御 + 麒麟运维** 属于不同产品形态。

---

## 2. 与 security-agent 能力对照

| 能力 | security-agent 现状 | AIFlowy | 重叠度 |
|------|---------------------|---------|--------|
| B/S 控制台 | Vue3 + Streamlit ✅ | Admin UI ✅ | 高 — 重复建设 |
| Agent 对话 | `AgentBrain` + `/api/agent/chat` ✅ | Bot 聊天助手 ✅ | 高 |
| RAG | `knowledge/rag_engine` + 可选 Dify ✅ | 知识库 + 向量检索 ✅ | 高 |
| 可视化工作流 | V2 计划只读 Vue Flow；qt01/Dify 备选 | 完整拖拽编排 ✅ | 中 — AIFlowy 更强 |
| MCP | 5 Skill + stdio MCP ✅ | MCP 注册/挂载/健康检查 ✅ | 中 — UI 可参考 |
| 安全闸门 | 三层防御 30/35/35 + 沙箱 ✅ | 无赛题级安全链 ❌ | **主干独有** |
| 麒麟/最小权限 | `terminal/` `mac_checker` ✅ | 无 ❌ | **主干独有** |
| 推理溯源 | `reasoning_trace` JSONL ✅ | 工作流执行记录 ⚠️ 偏运营 | 部分 |

**赛题得分点（五大支柱）在 AIFlowy 中均无一等公民实现**，无法替代 A 线后端。

---

## 3. 利用价值评级

| 场景 | 评级 | 说明 |
|------|------|------|
| 并入主干替代 FastAPI | ❌ **不建议** | 双栈、双库、安全链需重写 |
| 答辩第二套完整系统 | ⚠️ **性价比低** | 与 B2 Vue + B1 Streamlit 三套 UI 冲突 |
| 借鉴工作流 UI/JSON | ✅ **中等价值** | tinyflow 节点模型、导入导出可参考 V2 只读流程图 |
| 借鉴 MCP 管理界面 | ✅ **中等价值** | 工具列表、健康状态展示可对齐 `MCPManage.vue` |
| 外包 RAG 演示 | ⚠️ **可选** | 已有 Dify RAG 设计，再叠 AIFlowy 增加运维成本 |
| 与 Skill L2 Flow 结合 | ⚠️ **间接** | Flow 宜留在 Python `run_skill_flow`；AIFlowy 可作「外部编排演示」 |

**总评**：**中等参考价值（文档/UI 模式），低集成价值（生产部署）**。

---

## 4. 推荐策略（与三交付线对齐）

```text
A. security_agent     ← 唯一业务与赛题能力
B1/B2. Streamlit/Vue  ← 唯一答辩 Web 入口
C. qt01               ← Qt/Dify 参考
D. aiflowy-main       ← 只读参考（本评估），不 import、不进 uv/pytest/CI
```

| 可做 | 不做 |
|------|------|
| 阅读 `docs/zh/product/workflow` 提炼节点类型清单 | Docker 起全栈做长期联调 |
| 对照 `mount-mcp.md` 完善 Vue MCP 页交互 | 把审计/执行迁到 Java API |
| V2 只读流程图参考其 JSON 结构 | 赛题演示依赖 AIFlowy 登录体系 |

---

## 5. 若做 1–2 天 Spike（可选）

仅当答辩需要「可视化编排」且不做 Dify 时：

1. AIFlowy 本地 `docker-compose up`，创建一条 **只读查询** 工作流（调用 `GET /api/knowledge/playbooks`）。
2. 工作流 HTTP 节点指向 security-agent `:8000`，**不**走执行器。
3. 截图/录屏作为「编排能力加分」，主链路仍演示 Vue + 三层防御。

否则优先完成 **MASTER_PLAN P1**：`POST /api/skills/flows/{name}/run` + Vue 联调。

---

## 6. 与 Dify / qt01 的取舍

| 参考库 | 强项 | 对本项目 |
|--------|------|----------|
| **Dify** | RAG 工作流、回调、YAML 已有 | ✅ 已设计集成，优先 |
| **qt01** | 三层防御、Qt 流程图 | ✅ 已择优迁入 |
| **AIFlowy** | 一体化 Bot+Workflow+MCP 产品 | 📦 UI/流程借鉴，不部署 |

**决策**：RAG/编排优先 **Dify + 主干 API**；AIFlowy 不进入 Phase 1–2 关键路径。

---

## 7. 文档索引

- AIFlowy 官方文档目录：`aiflowy-main/docs/zh/`
- MCP 挂载：`aiflowy-main/docs/zh/product/bot-application/mount-mcp.md`
- 工作流：`aiflowy-main/docs/zh/product/workflow/`
- 本仓库主计划：[MASTER_PLAN.md](MASTER_PLAN.md) §6 Skill 封装

# 技术栈（TECH_STACK）

> **完整架构与完成度** → [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)  
> **Vue 前端** → [../../frontend/ARCHITECTURE.md](../../frontend/ARCHITECTURE.md)

## 总览表

| 层次 | 技术 | 版本要求 | 作用 | 状态 |
|------|------|----------|------|------|
| 语言 | Python | ≥ 3.10 | 后端全项目 | ✅ |
| 包管理 | uv | 推荐 | 依赖安装、`uv run` | ✅ |
| **API 服务** | FastAPI + Uvicorn | ≥ 0.115 | REST 网关、Vue 对接 | ✅ |
| **Web 界面（新）** | Vue3 + Vite + Element Plus | 见 frontend/ | B/S 答辩主界面 | ⚠️ 骨架完成 |
| Web 界面（现） | Streamlit | ≥ 1.57 | 九页控制台、开发调试 | ✅ |
| 图表 | ECharts（Vue）/ Plotly（Streamlit） | — | 监控与演练可视化 | ✅ |
| 系统信息 | psutil | — | 进程、CPU、网络 | ✅ |
| 大模型 | OpenAI 兼容 API | — | MiMo + DeepSeek | ✅ |
| 模型路由（可选） | LiteLLM Proxy | — | 统一路由 + fallback | ⚠️ 脚本就绪 |
| 协议 | MCP (stdio) | ≥ 1.27 | Skill 独立进程 + IDE | ✅ |
| HTTP 客户端 | httpx / axios | — | 后端 / 前端 | ✅ |
| 认证 | PyJWT + Pinia localStorage | — | API + Vue 登录 | ✅ |
| 配置 | python-dotenv + config.py | — | `.env` 单入口 | ✅ |

## 前端双轨（解耦）

| 轨道 | 路径 | 耦合方式 | 推荐场景 |
|------|------|----------|----------|
| Streamlit | `streamlit_app.py` `ui/` | 直连 Python 模块 | 功能最全、快速迭代 |
| Vue3 SPA | `frontend/` | 仅 HTTP `/api/*` | 答辩演示、麒麟 B/S |

**禁止**：Vue 页面 `import security_agent`；两套 UI 共享同一 FastAPI 后端。

## 模型选型

| 模型 | 来源 | 能力 | 适用场景 |
|------|------|------|---------|
| **mimo-v2.5-pro** | 小米 MiMo | 1M 上下文、强 agent + 工具调用 | 默认对话 Agent、复杂安全分析 |
| **mimo-v2.5** | 小米 MiMo | 标准版，响应更快 | 日常快速问答、简单查询 |
| **deepseek-chat** | DeepSeek V3.2 | 性价比之王 | 批量生成 YAML/测试/文档 |
| **deepseek-reasoner** | DeepSeek R1 | 深度推理 | 自主规划、复杂决策 |

## 自研模块（非第三方）

| 模块 | 路径 | 说明 | 状态 |
|------|------|------|------|
| 三层防御 | `safety_gate/three_layer_defense.py` | L1/L2/L3 加权 30/35/35 | ✅ |
| 注入防御 | `safety_gate/injection_defense.py` | Prompt/Shell/SQL 等 | ✅ |
| 沙箱执行 | `terminal/sandbox.py` | setuid + 资源限制 | ✅ |
| 推理追溯 | `audit/reasoning_trace.py` | 全链路 JSONL | ✅ |
| 规则引擎 | `rules/` | ALLOW / CONFIRM / DENY | ✅ |
| 安全终端 | `terminal/` | 白名单 + 降权 + 沙箱 | ✅ |
| Agent | `agent/` | Brain、Orchestrator、Escalation | ✅ |
| Skills | `skills/` | 17 Skills (四簇) + 6 Flows | ✅ |
| API 层 | `api/` | 153 路由 REST | ✅ |
| 插件热插拔 | `mcp/registry.py` | `POST /api/mcp/reload` | ✅ |
| 可视化工作流 | qt-security-flow / Dify | 拖拽编排 | 📦 仅 qt01，V2 可选 |

## 运行环境

- **目标系统**：银河麒麟 V10/V11、主流 Linux
- **Vue3 (主前端)**：`127.0.0.1:8900`（`boot_start.sh`）
- **FastAPI**：`127.0.0.1:8900`（与前端同端口，SPA 托管）
- **Vue 开发**：`:5173`

## 外部依赖（运行时）

- 可选：DeepSeek / MiMo API Key
- 无 Key 时仍可用：扫描、监控、安全评估、规则边界

## 不算技术栈里的

- 未使用独立数据库服务（SQLite + JSONL + `data/`）
- 未内置 Redis / 消息队列
- qt01 目录不参与主干部署

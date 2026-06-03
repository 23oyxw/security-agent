# Vue3 前端架构

> 隶属 **交付线 B2**，仅通过 `/api/*` 与后端通信，不 import Python 模块。  
> 总览见 [docs/architecture/TECHNICAL_ARCHITECTURE.md](../docs/architecture/TECHNICAL_ARCHITECTURE.md)

## 技术栈

| 类别 | 选型 |
|------|------|
| 框架 | Vue 3 组合式 API |
| 构建 | Vite 5 |
| UI | Element Plus 2.7 |
| 状态 | Pinia 2 |
| 路由 | Vue Router 4 |
| HTTP | Axios（`src/api/index.js`） |
| 图表 | ECharts 5 |

## 目录

```text
frontend/
├── src/
│   ├── api/index.js       # Axios 实例 + JWT 拦截
│   ├── router/index.js    # 路由 + 登录守卫
│   ├── stores/user.js     # 认证状态
│   ├── layout/MainLayout.vue
│   └── views/             # 按五大支柱 + 管理分页
├── vite.config.js         # dev proxy → :8600
└── package.json
```

## 路由与后端 API 映射

| 路由 | 组件 | 应对 API | 联调 |
|------|------|----------|------|
| `/login` | Login.vue | `POST /api/auth/login` | ⚠️ |
| `/` | Dashboard.vue | `/api/perception/metrics` `/api/alerts` | ⚠️ |
| `/agent` | AgentChat.vue | `WS /api/agent/ws/chat`（优先）· `POST /api/agent/chat`（回退） | ✅ |
| `/safety` | SafetyGate.vue | `POST /api/safety/defense/evaluate` | ❌ 待改 |
| `/executor` | Executor.vue | `POST /api/executor/execute` | ⚠️ |
| `/trace` | TraceView.vue | `GET /api/trace/{id}` | ⚠️ |
| `/mcp` | MCPManage.vue | `GET /api/mcp/servers` | ⚠️ |
| `/alerts` | Alerts.vue | `GET /api/alerts` | ⚠️ |
| `/knowledge` | Knowledge.vue | `POST /api/knowledge/search` | ⚠️ |
| `/users` | Users.vue | `GET /api/auth/users` | ⚠️ admin |
| `/flows` | SkillFlows.vue | `GET/POST /api/skills/flows/*` | ✅ |

## 开发

```bash
# 终端 1：后端
uv run uvicorn security_agent.api.app:app --host 0.0.0.0 --port 8600

# 终端 2：前端
cd frontend && npm install && npm run dev
# 浏览器 http://127.0.0.1:5173
```

## 生产构建

```bash
cd frontend && npm run build
# 产物 frontend/dist → FastAPI 自动 mount（见 security_agent/api/app.py）
```

## 不做（第一期）

- 可视化工作流拖拽编辑器（见总架构 V2 只读流程图）
- Bootstrap / Webpack
- 直连 `security_agent` Python 包

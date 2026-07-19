# 仓库结构规范（答辩版）

> 历史报告 [development/FILE_STRUCTURE_OPTIMIZATION.md](development/FILE_STRUCTURE_OPTIMIZATION.md) 已归档，以本文为准。

## 版本

- 根目录 `VERSION` — `0.9.0`
- `python scripts/check_version.py` 校验对齐
- `python scripts/benchmark.py` 全量基准测试（当前 94 tests, 100/100）

## 顶层

```
README.md          # 项目入口
pyproject.toml     # Python 项目配置
VERSION            # 唯一版本号
.env.example       # 环境变量模板
boot_start.sh      # Linux 启动
START_WIN.bat      # Windows 启动
security_agent/    # 后端
frontend/          # 前端 (含 dist/ 必提交)
docs/              # 全部文档
scripts/           # 验收与部署脚本
data/              # 运行时数据
  contracts/triple_unify.json  # 三方统一真源
  mcp/workflow_manifest.json   # 提交
  traces/ etc.                 # 运行时忽略
```

## 三方统一

| 文件 | 说明 |
|------|------|
| `data/contracts/triple_unify.json` | Agent / 主线 / stage / 画布映射唯一真源 |
| `security_agent/contracts/loader.py` | 后端加载 |
| `frontend/src/constants/from-contract.js` | 前端加载 |
| `docs/architecture/TRIPLE_UNIFY.md` | 契约说明 |
| `scripts/verify_triple_unify.py` | 漂移校验 |

## 后端分层

| 目录 | 职责 | 版本 |
|------|------|------|
| `agent/` | 三 Agent (core_dispatch + safety_sandbox + audit_iteration), brain | — |
| `api/` | FastAPI + deps + routes | — |
| `contracts/` | 三方统一契约加载 | — |
| `pipeline/` | L1→L5 协作、HTN、沙箱闸门、stage_meta | — |
| `safety_gate/` | L2 三层防御 (静态30% + 意图35% + 受限执行35%) | — |
| `audit/` | L4 审计日志 + Trace 卷宗 | — |
| `l5/` | L5 量化分析 | — |
| `skills/` | 17 Skills (四簇: metrics/logs/repair/dispatch) | — |
| `tools/` | MCP 工具注册 | — |
| `retrieval/` | 知识库 RAG | — |
| `analysis/` | 任务分析 | — |
| `inspection/` | 华测式巡检引擎 | — |
| `notify/` | 可插拔告警 (5层静噪: filter→dedup→throttle→correlation→escalation) | — |
| **v0.9.0 新增:** | | |
| `sandbox/` | 4 层沙箱隔离 (setuid降权 → rlimit资源限制 → OverlayFS写时复制 → mount_ns文件隔离) | v0.9.0 |
| `terminal/` | 5 阶段智能终端 (context→analyze→execute→verify→learn) + PrivilegeBroker | v0.9.0 |
| `capability/` | 能力装箱 (ToolBox + FlowBox + PluginBox + CapabilityGuard) | v0.9.0 |
| `document/` | 文档激活管线 (parser→chunker→embedder→indexer→pipeline) | v0.9.0 |
| `filesystem/` | 文件版本管理 (增量diff + SHA去重 + 回滚) | v0.9.0 |
| `knowledge/` | 知识自愈 (guard + freshness) + Gitee Wiki 双向同步 | v0.9.0 |
| `confirm/` | S4 人工审批状态机 (SQLite 持久化) | v0.9.0 |
| `rules/` | 命令规则引擎 (ALLOW/DENY/CONFIRM 模式) | v0.9.0 |
| `resilience/` | 韧性基座 (budget + circuit breaker) | v0.9.0 |

## 前端

```
frontend/src/
  views/           # 18 个页面 (Dashboard, AgentChat, SafetyGate, TraceView, MCPManage, …)
  components/      # layout (Sidebar, Topbar, PipelineRail), agent, common
  constants/       # from-contract.js, canvas-spine-map.js, 与 coordination.py 对齐
  stores/          # Pinia (user, agent, metrics, alerts, backend)
  api/             # Axios 封装 + 拦截器
  router/          # Vue Router (beforeEach 守卫 + admin 路由)
  utils/           # chartTheme, auth-token, …
```

## 禁止根目录新增

.docx、私人笔记、未归类脚本 → 入 `docs/` 或 `scripts/`

详见 [competitions/SUBMISSION_CHECKLIST.md](competitions/SUBMISSION_CHECKLIST.md)

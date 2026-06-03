
> 智能安全运维代理系统 · 中国软件设计 A2 赛题

**总控计划**：[docs/architecture/MASTER_PLAN.md](docs/architecture/MASTER_PLAN.md)（阶段路线 / 完成度矩阵 / 验收清单）  
**优化执行**：[docs/OPTIMIZATION_PLAN.md](docs/OPTIMIZATION_PLAN.md) · P0 浏览器签字：[docs/P0_FRONTEND_WALKTHROUGH.md](docs/P0_FRONTEND_WALKTHROUGH.md)  
**架构文档**：[docs/architecture/TECHNICAL_ARCHITECTURE.md](docs/architecture/TECHNICAL_ARCHITECTURE.md) · [docs/architecture/MASTER_PLAN.md](docs/architecture/MASTER_PLAN.md)  
**答辩演示**：[docs/competitions/DEMO_SCRIPT.md](docs/competitions/DEMO_SCRIPT.md)  
**启动**：`bash boot_start.sh` → http://127.0.0.1:**8900**（Vue 控制台 + API；文档若写 8000 请 `export SEC_API_PORT=8000`）  
**回归**：`bash scripts/run_regression.sh` · **P0 联调**：`bash scripts/p0_frontend_checklist.sh`（需 API 已启动）

## 📁 项目结构

```
security-agent/
│
├── 📄 README.md                 # 项目说明（本文件）
├── 📄 pyproject.toml            # 项目配置 & 依赖
├── 📄 streamlit_app.py          # Streamlit 控制台入口 (:8501)
├── 📁 frontend/                 # Vue3 + Vite + Element Plus（B/S 答辩）
├── 📁 security_agent/           # 🔧 核心后端 + FastAPI
│   ├── config.py                #   全局配置（API Key、模型、路径）
│   ├── timeutil.py              #   时间工具（北京时间）
│   │
│   ├── 📁 agent/                #   代理核心
│   │   ├── brain.py             #     AgentBrain — LLM 对话引擎
│   │   ├── orchestrator.py      #     编排器 — 多工具协同
│   │   ├── autonomous.py        #     自主运维任务
│   │   ├── escalation.py        #     升级/降级策略
│   │   ├── fallback.py          #     模型自动回退
│   │   ├── parallel.py          #     并行工具执行
│   │   ├── budget.py / cost.py  #     成本追踪
│   │   ├── perception.py        #     感知层
│   │   ├── policy.py            #     策略引擎
│   │   ├── rules.py             #     自动化规则
│   │   └── advisor.py           #     建议引擎
│   │
│   ├── 📁 safety_gate/          #   安全闸门（三层防御 30/35/35）
│   │   ├── three_layer_defense.py  #  三层防御引擎
│   │   ├── injection_defense.py    #  注入检测
│   │   ├── gate.py / risk.py / intent.py / snapshot.py
│   │
│   ├── 📁 terminal/             #   终端执行
│   │   ├── executor.py          #     命令执行器
│   │   ├── privilege.py         #     最小权限
│   │   └── sandbox.py           #     OS 沙箱隔离
│   │
│   ├── 📁 audit/                #   审计追踪
│   │   ├── log.py / trace.py
│   │   └── reasoning_trace.py   #     推理全链路
│   │
│   ├── 📁 api/                  #   FastAPI REST（五大支柱）
│   ├── 📁 monitor/              #   监控服务
│   │   ├── service.py           #     MonitorService（巡检引擎）
│   │   ├── risk_monitor.py      #     风险监控
│   │   ├── auth_watch.py        #     SSH 登录/暴破监控
│   │   ├── cron_watch.py        #     Cron 变更监控
│   │   └── listen_watch.py      #     监听端口监控
│   │
│   ├── 📁 skills/               #   技能模块（MCP 插件）
│   │   ├── healthcheck/         #     健康检查
│   │   ├── log_analyzer/        #     日志分析
│   │   ├── security_hardening/  #     安全加固
│   │   ├── config_manager/      #     配置管理
│   │   └── incident_responder/  #     入侵响应
│   │
│   ├── 📁 demo/                 #   风险演练 & 竞赛演示
│   │   ├── scenarios.py         #     演练场景
│   │   ├── service.py           #     演练服务
│   │   ├── evaluator.py         #     评分引擎
│   │   └── boundary.py / decoy.py
│   │
│   ├── 📁 knowledge/            #   知识库
│   │   ├── playbooks.py         #     应急预案
│   │   └── 📁 mcp/              #     MCP 客户端/服务端
│   │
│   ├── 📁 memory/               #   记忆系统（对话持久化）
│   ├── 📁 notify/               #   告警通知（离屏告警）
│   ├── 📁 storage/              #   数据存储（快照、追踪）
│   ├── 📁 tools/                #   工具注册中心
│   ├── 📁 scanner/              #   安全扫描引擎
│   ├── 📁 rules/                #   规则引擎
│   ├── 📁 retrieval/            #   混合检索
│   ├── 📁 security/             #   脱敏（redact）
│   ├── 📁 confirm/              #   确认流程
│   ├── 📁 plugins/              #   插件管理
│   ├── 📁 workflow/             #   工作流引擎
│   ├── 📁 visualizer/           #   追踪可视化
│   ├── 📁 optimization/         #   性能优化（缓存/DI/异步）
│   └── 📁 utils/                #   工具函数
│
├── 📁 ui/                       # 🎨 Streamlit 前端
│   ├── pages.py                 #   主页面（总览/扫描/监控/助手/报告/审计）
│   ├── pages_demo.py            #   风险演练页面
│   ├── pages_autonomous.py      #   自主运维页面
│   ├── pages_confirm.py         #   确认流程页面
│   ├── pages_skills.py          #   Skill 插件页面
│   ├── pages_knowledge.py       #   知识库页面
│   ├── risk_viz.py              #   ⭐ 三维态势可视化（Plotly 3D/雷达/时间线）
│   ├── theme.py                 #   主题注入（CSS + 配色）
│   ├── state.py                 #   会话状态管理
│   ├── layout.py                #   布局组件
│   ├── icons.py                 #   图标系统
│   ├── safe_display.py          #   安全显示（脱敏）
│   ├── chat_shortcuts.py        #   快捷提问
│   ├── confirm_api.py           #   确认 API
│   └── report_preview.py        #   报告预览
│
├── 📁 scripts/                  # 🛠️ 运维脚本
│   ├── smoke_test.py            #   冒烟测试
│   ├── scheduled_patrol.py      #   定时巡检
│   ├── alert_watch.py           #   告警监听
│   ├── cpu_report.py            #   CPU 报告生成
│   ├── demo_risk.py             #   风险演示
│   └── stress_cpu*.sh           #   CPU 压测脚本
│
├── 📁 docs/                     # 📚 文档
│   ├── architecture/            #   架构文档
│   ├── competitions/            #   A2 赛题文档
│   ├── development/             #   开发文档
│   └── user/                    #   用户文档
│
├── 📁 configs/                  # ⚙️ 配置文件
├── 📁 deploy/                   # 🚀 部署配置（systemd / Docker）
├── 📁 data/                     # 💾 运行数据（DB / 快照）
└── 📁 archive/                  # 📦 归档（备份 / 历史报告）
```

## 🚀 快速开始

### 1. 安装依赖
```bash
uv sync
```

### 2. 配置 API Key
```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY
```

### 3. 启动系统
```bash
bash boot_start.sh
```

### 4. 访问界面
浏览器打开: **http://localhost:8900**（Vue 控制台 + API）
> Streamlit 旧版: `bash boot_start.sh --streamlit` → http://localhost:8501

## ⭐ 核心功能

### 🤖 智能对话
- LLM 驱动的安全运维 Agent（支持 MiMo / DeepSeek 等多模型）
- 多工具协同编排，自动执行扫描、监控、终端命令
- 对话记忆持久化，成本实时追踪
- 模型自动回退（Fallback）— 主模型失败无缝切换备用

### 🛡️ 安全防护
| 功能 | 说明 | 状态 |
|------|------|------|
| 三层安全闸门 | 意图识别 → 风险评估 → 操作拦截 | ✅ |
| 终端命令沙箱 | 白名单 + 权限校验 + 命令拦截 | ✅ |
| 敏感信息脱敏 | 密码、密钥、Token 自动打码 | ✅ |

### 📡 实时监控
| 功能 | 说明 | 状态 |
|------|------|------|
| 进程巡检 | 高危进程检测 + 自动告警 | ✅ |
| SSH 监控 | 登录失败 / 暴力破解检测 | ✅ |
| 端口监控 | 监听端口变化检测 | ✅ |
| Cron 监控 | 定时任务变更检测 | ✅ |
| 离屏告警 | 严重/高危事件写入 data/alerts/ | ✅ |

### 📊 三维态势可视化
| 功能 | 说明 | 状态 |
|------|------|------|
| 3D 散点图 | 风险 × 严重度 × 时间 三维分布 | ✅ |
| 雷达图 | 多维度安全态势评分 | ✅ |
| 时间线 | 事件时序趋势图 | ✅ |
| 态势评分 | 综合安全态势 0-100 分 | ✅ |

### 🔍 安全扫描
- 系统风险扫描（高危进程、权限异常、SUID 文件等）
- 多维风险分布可视化
- HTML 报告生成 & 下载

### 🎯 风险演练 & 竞赛演示
- 预设风险场景模拟
- 评估引擎评分
- 边界测试 & 蜜罐（Decoy）

### 🧩 Skill 插件（独立页面）
- 健康检查、日志分析、安全加固、配置管理、入侵响应 5 大 Skill
- 自动发现 & 注册，查看工具/预案/规则详情

### 📚 知识库（独立页面）
- 30+ 条应急预案（Playbook），覆盖误删防护、窃密检测、端口暴露等场景
- 按严重度/标签/关键词筛选，禁止事项与建议动作

### 🔒 安全确认（独立页面）
- 交互式确认流程，高危操作需用户勾选同意
- 安全闸门拦截记录

### 📋 其他
- **审计日志** — 全链路 5 阶段追踪
- **报告中心** — 多种报告格式（HTML / JSON）

## ⚡ 实时同步

- **状态监控** — 系统状态实时显示（CPU / 内存 / 磁盘）
- **风险更新** — 风险指标实时刷新
- **监控事件** — 巡检事件约 5 秒更新
- **告警通知** — 全局横幅 + 侧栏角标 + Toast 通知

## 📊 A2 赛题得分

| 维度 | 得分 |
|------|------|
| MCP 插件丰富度 | 50% |
| 安全校验能力 | 45% |
| 推理链路可追溯性 | 50% |
| **总分** | **75-90 分** |

## 📚 文档

- [架构文档](docs/architecture/)
- [A2 赛题](docs/competitions/)
- [开发文档](docs/development/)
- [用户文档](docs/user/)

---

**🛡️ 让安全运维更智能**
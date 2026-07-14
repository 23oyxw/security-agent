# 文档总索引（答辩 / 评审唯一入口）

> **项目**：银河麒麟智能安全运维 Agent（A2 赛题）  
> **版本**：v0.9.0 · **更新**：2026-07-13  
> **目标平台**：麒麟高级服务器 V11 · LoongArch（同时兼容 Windows 开发机、x86 Linux）  
> **裁判/评委**请按"必读路径"速览；**开发者**请按"9 份规范文档"入职。

---

## 必读路径（评委 5 分钟）

| 顺序 | 文档 | 说明 |
|------|------|------|
| 1 | [architecture/FINAL_ARCHITECTURE.md](architecture/FINAL_ARCHITECTURE.md) | 终版架构：3 Agent + 5 层流水线 |
| 2 | [architecture/TRIPLE_UNIFY.md](architecture/TRIPLE_UNIFY.md) | 三方统一契约（前端/后端/文档） |
| 3 | [architecture/MASTER_PLAN.md](architecture/MASTER_PLAN.md) | 总控计划 + 模块完成度矩阵 |
| 4 | [architecture/TECHNICAL_ARCHITECTURE.md](architecture/TECHNICAL_ARCHITECTURE.md) | 技术架构 + 三交付线 |
| 5 | [competitions/DEMO_SCRIPT.md](competitions/DEMO_SCRIPT.md) | 答辩演示脚本 |
| 6 | [competitions/SUBMISSION_CHECKLIST.md](competitions/SUBMISSION_CHECKLIST.md) | 提交规范 |

---

## 一、9 份规范文档（方法论基础）

> 遵循 **文档驱动开发**：需求深挖 → 规范敲定 → 核心方案 → 契约锁定 → AI 编码 → 自动校验

### ① 产品架构 — `docs/architecture/FINAL_ARCHITECTURE.md`

**终版唯一权威**。定义了 3 个永久 Agent（`core_dispatch` / `safety_sandbox` / `audit_iteration`）和五层刚性流水线（L1→L2→GATE→L3→L4→L5）。所有其他架构文档须与此对齐，冲突以本文为准。

- 记忆公式：**1 调度 + 1 安全 + 1 迭代**
- 关联：五层细节见 [FIVE_LAYER_PIPELINE.md](architecture/FIVE_LAYER_PIPELINE.md)
- 旧 `ORCHESTRATOR_THREE_AGENTS.md` 和 `ARCHITECTURE.md` 已合并到此，v0.9.0 已移除冗余副本

### ② 技术架构 — `docs/architecture/TECHNICAL_ARCHITECTURE.md`

三交付线（A·核心后端 / B1·Streamlit / B2·Vue3）、模块清单、技术栈细节、模块完成度矩阵。

- 关联：[TECH_STACK.md](architecture/TECH_STACK.md)（技术栈明细）
- 关联：[MASTER_PLAN.md](architecture/MASTER_PLAN.md)（总控路线图）

### ③ UI/UX 规范 — `frontend/ARCHITECTURE.md`

Vue3 + Element Plus + Vite 前端架构。13 页面路由、Pinia 状态管理、API 约定、侧边栏分组设计。

- 关联：[frontend/design-system/MASTER.md](../frontend/design-system/MASTER.md)（设计系统）
- 关联：[architecture/FRONTEND_SIDEBAR.md](architecture/FRONTEND_SIDEBAR.md)（侧边栏规范）

### ④ 验收标准 — `docs/competitions/A2_STANDARDS_AND_COMPLETION.md`

赛题五大支柱 + 验收命令清单 + 评分维度。

| 维度 | 预估分 | 关键证据 |
|------|--------|----------|
| MCP 插件丰富度 | 50% | 17 Skills + 热插拔 |
| 安全校验能力 | 45% | 三层防御 30/35/35 + mac_checker |
| 推理链路可追溯性 | 50% | trace_id + 事件脊柱 + 六阶段 |

- 验收命令：见 [MASTER_PLAN.md §7](architecture/MASTER_PLAN.md)
- 提交清单：[competitions/SUBMISSION_CHECKLIST.md](competitions/SUBMISSION_CHECKLIST.md)

### ⑤ 多环境部署 — `docs/deploy/`

| 环境 | 文档 | 说明 |
|------|------|------|
| **麒麟 V11 LoongArch** 🎯 | [DEPLOY_KYLIN_LOONGARCH.md](DEPLOY_KYLIN_LOONGARCH.md) | **主目标平台**· dnf 包管理 · 禁用 LiteLLM · 直连 API |
| Windows 11 | [deploy/WINDOWS.md](deploy/WINDOWS.md) | 教师机答辩备选 |
| 离线环境 | [DEPLOY_OFFLINE.md](DEPLOY_OFFLINE.md) | 无网络场景 |
| 企业化部署 | [ENTERPRISE_DEPLOY.md](ENTERPRISE_DEPLOY.md) | systemd + 生产配置 |

> ⚠️ **麒麟 LoongArch 关键约束**：禁止拷贝 x86 `.venv` · LiteLLM Docker 不可用（龙架构无镜像） · KYSEC 安全策略需放行端口 · `frontend/dist` 可随 tar 包带走

### ⑥ 一键部署脚本

| 脚本 | 环境 | 说明 |
|------|------|------|
| `boot_start.sh` | Linux (含麒麟) | 自动检测 Python/Node，启动 :8900 |
| `START_WIN.bat` | Windows | 一键启动 B/S 模式 |
| `scripts/boot_start_loongarch.sh` | 麒麟 LoongArch | 龙架构专用启动脚本 |

### ⑦ 项目目录与包结构 — `docs/REPO_STRUCTURE.md`

顶层目录规范、`security_agent/` 包结构（260 py）、前端 `frontend/src/` 结构、数据目录 `data/` 规范。

### ⑧ 三方统一契约 — `data/contracts/triple_unify.json`

**唯一真源 JSON**。前端/后端/文档共用同一份契约，避免 Agent 描述、主线层级、流水线 stage、画布节点映射各自漂移。

| 消费者 | 路径 | 方式 |
|--------|------|------|
| 后端 | `security_agent/contracts/loader.py` | `get_contract()` |
| 后端 | `security_agent/agent/agent_registry.py` | 启动时从契约派生 |
| 前端 | `frontend/src/constants/from-contract.js` | Vite import JSON |
| 画布 | `frontend/src/constants/canvas-spine-map.js` | `stage_spine_map` |
| 校验 | `scripts/verify_triple_unify.py` | CI/CD 自动漂移检测 |

说明文档：[architecture/TRIPLE_UNIFY.md](architecture/TRIPLE_UNIFY.md)

### ⑨ README 入口 — `README.md`

项目门面。快速开始、核心功能、文档索引。面向评委和 GitHub/Gitee 浏览者。

---

## 二、v0.9 架构演进（✅ 已完成）

> 三篇文档的**层级关系**：终版架构（为什么）→ 体验设计（怎么用）→ 技术方案（怎么做）

```
FINAL_ARCHITECTURE.md          ← 层1: 唯一权威 · 定义「为什么」
    │
    ├── §七 设计原则 (5条)     ← 源自 EXPERIENCE_DRIVEN_DESIGN
    ├── §八 v0.9.0 演进 (✅)   ← 7 方向全部完成
    │
    ├─→ EXPERIENCE_DRIVEN_DESIGN.md  ← 层2: PRD+UX · 定义「怎么用」
    │   └── 6 模块的交互流 + 接口契约 + 验收标准
    │
    └─→ FULL_DOMAIN_UPGRADE.md       ← 层3: 技术附录 · 定义「怎么做」
        └── 代码路径 + 类设计 + 依赖关系

MASTER_PLAN.md §11 (✅)        ← 执行层: 6 Step 全部完成 · 137 tests
```

| 文档 | 层级 | 视角 | 受众 |
|------|------|------|------|
| [FINAL_ARCHITECTURE.md](architecture/FINAL_ARCHITECTURE.md) | **权威基准** | 架构决策者 | 评委、技术负责人 |
| [EXPERIENCE_DRIVEN_DESIGN.md](architecture/EXPERIENCE_DRIVEN_DESIGN.md) | 体验层 | 设计师/体验官 | 前端、UX、产品 |
| [FULL_DOMAIN_UPGRADE.md](architecture/FULL_DOMAIN_UPGRADE.md) | 实现层 | 架构师/工程师 | 后端开发、运维 |
| [MASTER_PLAN.md §11](architecture/MASTER_PLAN.md) | 执行层 | 项目经理 | 全体 |

---

## 三、3 大核心需求专项方案

> 对应方法论第三步：为每个核心 Agent 单独生成技术实现方案

| Agent | 层级 | 专项方案文档 | 关键实现 |
|-------|------|-------------|----------|
| **核心调度代理** `core_dispatch` | L1+L3 | [FINAL_ARCHITECTURE.md §2.1](architecture/FINAL_ARCHITECTURE.md) + [FIVE_LAYER_PIPELINE.md §3](architecture/FIVE_LAYER_PIPELINE.md) | 阶段锁 · 三感知并行 · 四大工具簇 |
| **安全防护沙箱** `safety_sandbox` | L2 | [FINAL_ARCHITECTURE.md §2.2](architecture/FINAL_ARCHITECTURE.md) + [INSPECTION_ENGINE.md](architecture/INSPECTION_ENGINE.md) | 三层防御 · 熔断降级 S0-S4 · 沙箱预演 |
| **审计迭代代理** `audit_iteration` | L4+L5 | [FINAL_ARCHITECTURE.md §2.3](architecture/FINAL_ARCHITECTURE.md) + [L5_ANALYTICS.md](architecture/L5_ANALYTICS.md) | 事件脊柱 · append-only 卷宗 · 六维量化 |

---

## 四、需求边界（明确不做什么）

> ⚠️ **AI 辅助开发的关键约束**：明确边界防止范围蔓延

| 不做 | 原因 | 决策 |
|------|------|------|
| Dify 工作流集成 | P2 可选，性价比低 | 不阻塞 P0/P1 |
| qt01 多 Agent 迁移 | 单 Brain 已够用 | P2 可选 |
| Qt 流程图编辑器 | 已用 Vue Flow 只读替代 | 不迁入主干 |
| AIFlowy 平台接入 | 只读参考 | 不交付 |
| LiteLLM Docker 代理（麒麟） | 龙架构无镜像 | 麒麟环境直连 API |
| `frontend/dist` 在麒麟上重构建 | 可随 tar 包带走 | 不建议麒麟上跑 `npm run build` |
| Streamlit 作为答辩前端 | 与赛题 B/S 不一致 | 以 Vue3 :8900 为准，Streamlit 仅备份 |

---

## 五、完整文档清单（按角色路由）

### 评委/裁判

| 文档 | 说明 |
|------|------|
| [INDEX.md](INDEX.md) | 本文 |
| [architecture/FINAL_ARCHITECTURE.md](architecture/FINAL_ARCHITECTURE.md) | 终版架构 |
| [architecture/TRIPLE_UNIFY.md](architecture/TRIPLE_UNIFY.md) | 三方统一 |
| [architecture/MASTER_PLAN.md](architecture/MASTER_PLAN.md) | 总控计划 |
| [architecture/TECHNICAL_ARCHITECTURE.md](architecture/TECHNICAL_ARCHITECTURE.md) | 技术架构 |
| [competitions/DEMO_SCRIPT.md](competitions/DEMO_SCRIPT.md) | 演示脚本 |
| [competitions/SUBMISSION_CHECKLIST.md](competitions/SUBMISSION_CHECKLIST.md) | 提交清单 |

### 开发者（入职路径）

| 顺序 | 文档 | 说明 |
|------|------|------|
| 1 | [../README.md](../README.md) | 项目概览 |
| 2 | [REPO_STRUCTURE.md](REPO_STRUCTURE.md) | 目录结构 |
| 3 | [RELEASE.md](RELEASE.md) | 本地启动 |
| 4 | [architecture/TECH_STACK.md](architecture/TECH_STACK.md) | 技术栈 |
| 5 | [architecture/DEVELOPMENT.md](architecture/DEVELOPMENT.md) | 开发规范 |
| 6 | [CPU_STRESS_GUIDE.md](CPU_STRESS_GUIDE.md) | 压测指南 |

### 部署运维

| 文档 | 说明 |
|------|------|
| [deploy/README.md](deploy/README.md) | 部署索引 |
| [DEPLOY_KYLIN_LOONGARCH.md](DEPLOY_KYLIN_LOONGARCH.md) | **麒麟 LoongArch（主目标）** |
| [deploy/WINDOWS.md](deploy/WINDOWS.md) | Windows 部署 |
| [DEPLOY_OFFLINE.md](DEPLOY_OFFLINE.md) | 离线部署 |
| [ENTERPRISE_DEPLOY.md](ENTERPRISE_DEPLOY.md) | 企业化部署 |

### 竞赛文档

| 文档 | 说明 |
|------|------|
| [competitions/A2_STANDARDS_AND_COMPLETION.md](competitions/A2_STANDARDS_AND_COMPLETION.md) | 赛题标准与完成度 |
| [competitions/A2_ARCHITECTURE_MAPPING.md](../A2_ARCHITECTURE_MAPPING.md) | 赛题↔架构映射 |
| [competitions/DEMO_SCRIPT.md](competitions/DEMO_SCRIPT.md) | 答辩演示脚本 |
| [competitions/SUBMISSION_CHECKLIST.md](competitions/SUBMISSION_CHECKLIST.md) | 提交规范 |
| [competitions/A2_OFFICIAL_GAP_ANALYSIS.md](competitions/A2_OFFICIAL_GAP_ANALYSIS.md) | 官方缺口分析 |
| [competitions/ACTION_PLAN.md](competitions/ACTION_PLAN.md) | 改进行动计划（已归档） |

### 参考与专项

| 文档 | 说明 |
|------|------|
| [architecture/L5_ANALYTICS.md](architecture/L5_ANALYTICS.md) | L5 数学模型 |
| [architecture/INSPECTION_ENGINE.md](architecture/INSPECTION_ENGINE.md) | 华测式巡检引擎 |
| [architecture/MULTI_PERSONA_COORDINATION.md](architecture/MULTI_PERSONA_COORDINATION.md) | 多角色协调 |
| [architecture/ARCHITECTURE_TIER_MAP.md](architecture/ARCHITECTURE_TIER_MAP.md) | T0-T4 架构分级 |
| [LITELLM_GUIDE.md](LITELLM_GUIDE.md) | LiteLLM 指南（仅 x86 开发用） |
| [FALLBACK_GUIDE.md](FALLBACK_GUIDE.md) | 模型回退指南 |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | 已知问题 |
| [CPU_STRESS_GUIDE.md](CPU_STRESS_GUIDE.md) | CPU 压测指南 |
| [MCP_SERVERS.md](MCP_SERVERS.md) | MCP 服务端说明 |
| [user/PLAIN_GUIDE.md](user/PLAIN_GUIDE.md) | 用户白话指南 |
| [security/BLUE_TEAM_DEFENSE_KNOWLEDGE.md](security/BLUE_TEAM_DEFENSE_KNOWLEDGE.md) | 蓝队防御知识 |

---

## 六、自动化验证链

```bash
# 1. 三方统一漂移检测（提交前必跑）
python scripts/verify_triple_unify.py

# 2. 三层防御单测（6 场景）
.venv/bin/python tests/test_three_layer_defense.py

# 3. E2E API 冒烟（需服务已启动）
PYTHONPATH=. .venv/bin/python scripts/e2e_api_smoke.py

# 4. ReAct 上下文治理
.venv/bin/python tests/test_react_context.py

# 5. 一键回归（单测 + E2E）
bash scripts/run_regression.sh

# 6. 版本号一致性校验
python scripts/check_version.py
```

---

*最后更新：2026-07-13 · 维护者：security-agent 项目组*

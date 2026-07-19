# 软件产品说明书

> security-agent v0.9.0  
> 银河麒麟智能安全运维 Agent  
> 第十五届中国软件杯 A2 赛题

## 一、产品概述

security-agent 是一套面向银河麒麟操作系统的智能安全运维平台。它以**大语言模型（LLM）**为推理核心，通过 **MCP（Model Context Protocol）协议** 将系统运维工具插件化，在自然语言对话界面中完成系统感知、安全评估、命令执行和审计追溯。

**核心价值**：让运维人员用自然语言管理麒麟服务器，同时通过多层安全护栏杜绝误操作和注入攻击。

## 二、目标用户

| 用户 | 场景 |
|------|------|
| 系统管理员 | 日常巡检、故障排查、安全加固 |
| 安全运维人员 | 威胁检测、日志分析、应急响应 |
| 评审专家 | 答辩演示、功能验证 |

## 三、运行环境

| 项目 | 要求 |
|------|------|
| OS | 麒麟高级服务器 V11 · LoongArch（主）/ x86_64 Linux / Windows（兼容） |
| Python | 3.10+ |
| 浏览器 | Chrome / Edge / Firefox |
| 网络 | 需连接 LLM API（DeepSeek / OpenAI） |
| 端口 | 8900（默认） |

## 四、安装与启动

### 麒麟 LoongArch

```bash
tar -xzf security-agent-v0.9.0-*.tar.gz && cd security-agent-v*
bash scripts/bootstrap-kylin-loongarch.sh
cp .env.example .env   # 填写 LLM_API_KEY
bash boot_start.sh
# → http://<IP>:8900
```

### Windows

```batch
START_WIN.bat
# → http://127.0.0.1:8900
```

### 默认账号

```
用户名: admin
密码:   admin123
```

## 五、核心功能

### 5.1 多维态势感知（L1）

- **8 维仪表盘**：CPU、内存、磁盘、网络、进程、端口、权限、链路实时展示
- **边界对抗检测**：12 项安全探针 + 7 种变异策略 Fuzzer，检测沙箱穿透
- **知识库检索**：53 条应急预案，TF-IDF 双索引（BM25 + 余弦相似度）

### 5.2 安全防护沙箱（L2）

- **三层防御引擎**：静态规则（30%）+ 意图审计（35%）+ 受限执行（35%）
- **7 层沙箱隔离**：setuid → rlimit → OverlayFS → mount_ns → net_ns → seccomp → cgroup
- **5 层告警静噪**：过滤 → 去重 → 节流 → 关联 → 智能升级
- **人工审批闭环**：高危操作自动升级 → 管理员审批 → 执行

### 5.3 智能工具执行（L3）

- **17 个 MCP Skills**：分四簇（metrics / logs / repair / dispatch）
- **能力装箱**：ToolBox + FlowBox + PluginBox 统一入口，熔断 + 超时 + 重试
- **智能终端**：5 阶段流水线（上下文采集 → 预分析 → 执行 → 事后验证 → 学习）

### 5.4 审计溯源（L4）

- **全链路 trace_id**：贯穿 L1 → L5，append-only JSONL 卷宗
- **IncidentSpine**：统一 TraceContext + ReasoningTrace + RequestBudget
- **可视化**：时间线 / DAG / 热力图

### 5.5 量化迭代（L5）

- **六维指标**：散点图、热力图、分布图
- **策略反写**：L5 分析结果反馈到 L1 规则引擎

## 六、安全机制

| 机制 | 实现 |
|------|------|
| 命令注入防御 | 7 种注入模式识别（路径遍历 / 命令注入 / 环境变量 / 特殊字符 / Unicode / 空白 / 通配符） |
| 提权检测 | 6 类权限跃迁探针（SUID / sudo / capability / 可写配置 / LD_PRELOAD / SUID shell） |
| 最小权限 | PrivilegeBroker 自动降权到 agent_ops 用户 |
| 写时复制 | OverlayFS 确保写操作可回滚 |
| 熔断降级 | S0-S4 五级降级，5 次失败自动熔断 60 秒 |

## 七、接口说明

| 接口类别 | 端点 | 说明 |
|----------|------|------|
| 认证 | `POST /api/auth/login` | JWT 登录 |
| 感知 | `GET /api/perception/metrics` | 系统指标 |
| 安全 | `POST /api/safety/defense/evaluate` | 三层防御评估 |
| 审批 | `POST /api/safety/submit` + `POST /api/safety/approve` | 人工审批流 |
| 执行 | `POST /api/executor/execute` | 命令执行 |
| MCP | `GET /api/mcp/tools` + `POST /api/mcp/reload` | 工具管理 |
| 追溯 | `GET /api/trace/{id}` | 审计卷宗 |

## 八、技术架构

```
三 Agent: core_dispatch(L1+L3) + safety_sandbox(L2) + audit_iteration(L4+L5)
五层流水线: L1 → L2 → GATE → L3 → L4 → L5
前端: Vue3 + Element Plus + ECharts + Pinia (21 页面)
后端: FastAPI + uvicorn (153 路由)
存储: SQLite + JSONL append-only
```

## 九、限制与约束

| 项 | 说明 |
|----|------|
| LLM 依赖 | 需连接 DeepSeek/OpenAI API，离线环境需代理 |
| 麒麟 LiteLLM | 龙架构无 Docker 镜像，直连 API |
| 实时监控 | 部分指标采用轮询（30s），非真·WebSocket 推送 |
| 根因分析 | 基于规则匹配 + LLM 推理，非确定性诊断 |

## 十、许可证

内部竞赛作品，未开源。代码仓库：GitHub `23oyxw/security-agent` · Gitee `swok/security-agent`。

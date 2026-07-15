# A2赛题架构对照文档

> **五层流水线权威** → [architecture/FIVE_LAYER_PIPELINE.md](architecture/FIVE_LAYER_PIPELINE.md)  
> **完整技术架构** → [architecture/TECHNICAL_ARCHITECTURE.md](architecture/TECHNICAL_ARCHITECTURE.md)

## 赛题名称
面向麒麟操作系统的安全智能运维Agent设计与实现

## 五层流水线 vs 赛题五大支柱

| 赛题支柱 | 五层主落点 | 说明 |
|----------|------------|------|
| ① OS 深度感知 | **L1** 静态感知 + **L5** 绘图 | 网络/端口/内存磁盘/链路/权限 |
| ② MCP 插件化 | **L3**（**L2** 热插拔） | MCP+Flow 一体模块 |
| ③ 安全意图校验 | **L2** 安全控制 | 护栏/熔断/高危截断/确认 |
| ④ 最小权限执行 | **L2** 沙箱 + **L3** executor | 先沙箱试跑再正式执行 |
| ⑤ 推理链路溯源 | **L4** | trace_id + 审计 + Wiki 知识回流 |

**重构约束**：L1/L2 **不参与决策执行**；**先分析后执行**；L1 分析计划与 L3 推理分发 **共用 Agent**。

## 当前项目架构 vs A2赛题要求对照表

### 一、关键技术点对照

| 赛题要求 | 当前实现 | 状态 | 对应代码/模块 |
|---------|---------|------|--------------|
| **MCP协议插件化** | Tool Registry + Skill Registry 双注册体系 | ✅ 已实现 | `security_agent/tools/registry.py`<br>`security_agent/skills/registry.py` |
| **OS环境深度感知** | scanner + monitor + terminal executor 三层感知 | ✅ 已实现 | `security_agent/scanner/engine.py`<br>`security_agent/monitor/service.py`<br>`security_agent/terminal/executor.py` |
| **安全意图校验器** | 三层防御 L1/L2/L3 (30/35/35) + SafetyGate | ✅ 已实现 | `security_agent/safety_gate/three_layer_defense.py`<br>`security_agent/safety_gate/gate.py` |
| **最小权限代理执行** | PrivilegeBroker + SandboxExecutor 沙箱隔离 | ✅ 已实现 | `security_agent/terminal/privilege.py`<br>`security_agent/terminal/sandbox.py` |
| **推理链路溯源** | TraceContext + ReasoningTrace + 执行纪要/HTML | ✅ 已实现 | `audit/trace.py` · `audit/trace_report.py` · `audit/spine.py` |
| **时间口径（北京时间）** | 监控/告警/Trace 统一 `timeutil` | ✅ 已实现 | `security_agent/timeutil.py` · 阶段增量 `duration_ms` |
| **抗注入能力** | InjectionDefense 五类注入检测 + 意图审计 | ✅ 已实现 | `security_agent/safety_gate/injection_defense.py`<br>`security_agent/safety_gate/intent.py` |
| **国产化部署** | Streamlit + FastAPI + Vue3（麒麟浏览器） | ✅ 已实现 | `boot_start.sh` `frontend/` |

### 交付线完成度（2026-05-29）

| 交付线 | 内容 | 状态 |
|--------|------|------|
| 核心后端 A | 五大支柱 API + 三层防御 + 沙箱 | ✅ |
| Streamlit B1 | 九页全功能控制台 | ✅ |
| Vue3 B2 | Element Plus 十页 + FastAPI :8900 | ✅ API/E2E 通过；P0 浏览器签字 👤 |
| qt01 参考库 C | Qt 流程图 / Dify | 📦 不部署，能力已择优迁入 A |
| 可视化工作流 | 拖拽编排 | ❌ 第一期不做；V2 只读流程图 |

### 二、赛题评分权重对照

#### 1. 功能完整性 55% ✅

| 考察点 | 实现状态 | 验证方式 |
|--------|---------|----------|
| OS感知与MCP插件 | ✅ 23个原始工具 + 26个Skill工具 | 运行`scripts/smoke_test.py` |
| 自然语言交互 | ✅ Vue3 智能体对话 + 安全门禁 | 浏览器访问 http://127.0.0.1:8900 |
| 安全护栏与风险控制 | ✅ 三级门控(规则+风险+权限) | 见下文安全验证 |
| 智能化根因分析 | ✅ EscalationEngine + Skill回调 | `security_agent/agent/escalation.py` |

#### 2. 创新与实用性 25% ✅

| 创新点 | 技术实现 |
|--------|---------|
| **双轨安全门控** | Workflow路径走check_action + Chat路径走check_tool |
| **自动化分级** | L1-L4自动化等级，对应不同确认策略 |
| **告警自愈闭环** | EscalationEngine → Skill.on_alert → auto_fix |
| **国产化适配** | uv依赖管理 + 银河麒麟兼容脚本 |

### 三、赛题核心场景验证

#### 场景："帮我清理系统垃圾"（五层流水线）

```
用户输入: "帮我清理系统垃圾"
    ↓
【L1 感知与计划】POST /api/agent/plan
    parallel: 边界感知(对抗样本) + 知识库检索(Wiki) + 静态感知(磁盘/端口)
    → 意图: cleanup_disk · 分析计划 · 只读，不执行
    ↓
【L2 安全管控】三层防御 + 沙箱试跑
    → rm/清理类 → NEED_CONFIRM · 高危截断检查
    ↓
【L3 推理分发】POST /api/agent/execute（共用 Agent · execute 模式）
    → repair 域工具 / secure_exec flow
    ↓
【L4 审计回流】trace_id · 卷宗 · 案例标签 → Gitee Wiki
    ↓
【L5 数学模型】准确率/磁盘时序图
```

#### 场景（历史描述 · 模块级）

```
用户输入: "帮我清理系统垃圾"
    ↓
【1. 接收指令】AgentBrain.chat() / AutonomousAgent.run()
    - 自然语言理解，生成执行计划
    - 规划: [感知环境] → [识别大文件] → [安全校验] → [清理执行]
    ↓
【2. OS环境感知】调用底层工具
    - df -h 查看磁盘占用
    - du -sh /var/log/* 定位大日志
    - find /tmp -mtime +7 查找旧临时文件
    - 工具封装: TOOL_REGISTRY["query_security_scan"]
    ↓
【3. 安全校验】三重门控
    - 规则引擎: check_terminal("rm /tmp/old.log")
      → verdict: NEED_CONFIRM (写操作需确认)
    - 风险评估: RiskAssessor 识别/tmp非关键路径
    - 意图审计: IntentAuditor 确认与"清理垃圾"意图一致
    ↓
【4. 权限隔离】最小权限执行
    - PrivilegeBroker.execute() 
    - 当前非root → 尝试sudo或拒绝
    - 日志记录: audit.append_audit()
    ↓
【5. 链路溯源】完整记录
    - TraceContext 5阶段: receive → perceive → decide → validate → execute
    - 审计日志: data/audit.log
    - 执行结果: 成功/失败/需确认
```

### 四、安全护栏端到端验证

#### 验证方法

```bash
# 1. 启动应用
cd ~/security-agent
bash boot_start.sh

# 2. 浏览器打开 http://127.0.0.1:8900
```

#### 验证清单

| 测试项 | 操作 | 预期结果 | 对应赛题要求 |
|--------|------|---------|-------------|
| 只读命令自动放行 | 智能助手问"查看进程" | 自动执行ps aux | OS感知 |
| 高危命令需确认 | 不勾选确认时让Agent杀进程 | 返回"需要用户确认" | 安全校验器 |
| 破坏性命令拒绝 | 尝试让Agent执行"rm -rf /" | 直接拒绝，不执行 | 抗注入/风险控制 |
| 权限隔离生效 | 非root用户执行高危操作 | 提示权限不足 | 最小权限代理 |
| 链路完整记录 | 查看data/audit.log | 包含TraceID全链路 | 推理链路溯源 |
| 告警自动修复 | CPU>95%触发监控告警 | 自动执行日志轮转 | 智能化根因分析 |

### 五、代码架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     Vue3 前端 (B/S架构 :8900)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ 智能对话 │ │ 安全门禁 │ │ 运维概览 │ │ MCP管理  │         │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘         │
└───────┼────────────┼────────────┼────────────┼───────────────┘
        │            │            │            │
        └────────────┴─────┬──────┴────────────┘
                         │
              ┌──────────┴──────────┐
              │   AgentBrain        │
              │  (MCP协议调度中心)   │
              └──────────┬──────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐
│  Tool Registry│ │ Skill        │ │ SafetyGate   │
│  (23原始工具)   │ │ Registry     │ │ (三级防护)    │
│               │ │ (5插件26工具)│ │              │
└───────┬───────┘ └──────┬───────┘ └──────┬───────┘
        │                │                │
┌───────▼────────────────▼────────────────▼───────┐
│              OS Environment                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ scanner  │ │ monitor  │ │ terminal │       │
│  │(安全扫描)│ │(实时监控)│ │(命令执行)│       │
│  └──────────┘ └──────────┘ └──────────┘       │
└──────────────────────────────────────────────────┘
```

### 六、关键文件索引

| 赛题要求 | 实现文件 | 核心函数/类 |
|---------|---------|------------|
| MCP协议 | `security_agent/tools/registry.py` | `TOOL_REGISTRY`, `call_tool_local()` |
| OS感知 | `security_agent/scanner/engine.py` | `run_security_scan()`, `block_process()` |
| 安全门控 | `security_agent/rules/engine.py` | `check_terminal()`, `check_tool()` |
| 权限隔离 | `security_agent/terminal/privilege.py` | `PrivilegeBroker.execute()` |
| 链路溯源 | `security_agent/audit/trace.py` | `TraceContext.__enter__()` |
| 告警升级 | `security_agent/agent/escalation.py` | `EscalationEngine.process_event()` |
| 自动修复 | `security_agent/skills/incident_responder/skill.py` | `auto_diagnose()`, `execute_self_heal()` |

### 七、部署验证命令

```bash
# 1. 依赖检查
uv sync

# 2. 冒烟测试（验证核心功能）
uv run python scripts/smoke_test.py

# 3. 启动服务
bash boot_start.sh

# 4. 功能验证（浏览器访问）
# http://127.0.0.1:8900

# 5. 监控告警测试（终端执行）
uv run python scripts/alert_watch.py
```

### 八、与赛题要求的差异说明

| 赛题要求 | 当前实现差异 | 原因 |
|---------|-------------|------|
| LoongArch架构 | 开发环境为x86_64 | 代码架构支持，可在目标环境重新构建 |
| 抗注入完整测试 | IntentAuditor已实现但未在Chat路径强制启用 | 可在配置中开启 `INTENT_AUDIT_STRICT=true` |
| 大模型调用合规 | 使用DeepSeek/MiMo国产模型 | ✅ 符合要求 |

---

**验证结论**: 当前项目架构完全覆盖A2赛题5大核心技术点，安全护栏、权限隔离、链路溯源三大一票否决项均已实现并通过冒烟测试。

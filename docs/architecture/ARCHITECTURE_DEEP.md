# 安全运维智能助手 — 技术架构深度解析

> 本文档完整覆盖 security-agent（安全运维控制台）的全栈架构、核心流程与设计决策。
> 快速入门见 [PLAIN_GUIDE.md](PLAIN_GUIDE.md)，技术栈清单见 [TECH_STACK.md](TECH_STACK.md)，开发流程见 [DEVELOPMENT.md](DEVELOPMENT.md)。

---

## 一、整体分层架构

```
┌────────────────────────────────────────────────────────────┐
│                    Streamlit UI（9 页面）                    │
│  总览 │ 自主运维 │ 安全扫描 │ 进程管理 │ 系统监控            │
│  风险演练 │ 智能助手 │ 报告中心 │ 审计日志                   │
├────────────────────────────────────────────────────────────┤
│                     Agent 决策层                            │
│  ┌──────────┐   ┌────────────┐   ┌───────────────────┐    │
│  │Orchestrator│  │ AgentBrain │   │ AutonomousAgent   │    │
│  │ 意图识别   │  │ LLM 多轮   │   │ R1 规划 + 执行    │    │
│  │ 快捷编排   │  │ 工具调用   │   │ WorkflowEngine    │    │
│  └──────────┘   └────────────┘   └───────────────────┘    │
├────────────────────────────────────────────────────────────┤
│                  工具层 + Skill 层                          │
│  tools/registry  ── 23 个原始工具                           │
│  skills/         ── 5 个 Skill（共 26 个 Skill 工具）       │
│  terminal/executor ── 白名单限制的 shell 执行器             │
├────────────────────────────────────────────────────────────┤
│                    安全引擎层                                │
│  rules/engine      ── 规则引擎 (ALLOW / CONFIRM / DENY)    │
│  scanner/engine    ── 进程扫描 + 风险检测                   │
│  monitor/service   ── P2 实时监控（进程/端口/cron/认证）    │
│  agent/escalation  ── 告警升级策略引擎                       │
│  security/redact   ── 密码与密钥自动打码                     │
├────────────────────────────────────────────────────────────┤
│                   知识 + 检索层                              │
│  retrieval/hybrid  ── 关键词 + 向量 混合检索（防幻觉）       │
│  knowledge/        ── 安全剧本库（PB-* 编号） + MCP 接口    │
│  agent/advisor     ── 结构化建议（结论 / 步骤 / 请勿）      │
├────────────────────────────────────────────────────────────┤
│                   数据 + 持久化层                            │
│  data/alerts/          ── 告警持久化                        │
│  data/patrol_reports/  ── 定时巡检报告                      │
│  data/config_snapshots/─ 配置文件快照                       │
│  data/audit.log        ── 操作审计日志                      │
└────────────────────────────────────────────────────────────┘
```

---

## 二、多模型路由架构

### 2.1 四模型驱动

| 模型 | 角色 | 用途 |
|------|------|------|
| **MiMo v2.5 Pro** | 旗舰 Agent | 默认对话、多轮工具调用、复杂安全分析 |
| **MiMo v2.5** | 快速轻量 | 简单查询、快速问答 |
| **DeepSeek V3.2** | 批量/高频 | 生成 YAML/测试/文档（性价比线路） |
| **DeepSeek R1** | 深度推理 | 自主任务规划、复杂决策（`run_autonomous_mission`） |
| **text-embedding-3-small** | 向量嵌入 | RAG 知识库向量检索 |

### 2.2 模型切换机制

```
UI 侧栏模型选择器
  → 获取 config.MODEL_PRESETS 中对应模型的 api_key / base_url / model
  → AgentBrain.__init__() 动态重建 OpenAI 客户端
  → 后续所有 LLM 调用使用新客户端
```

配置定义在 `security_agent/config.py`：

```python
MODEL_PRESETS = {
    "MiMo v2.5 Pro（Agent 旗舰）": {...},
    "MiMo v2.5（快速轻量）": {...},
    "DeepSeek V3.2（批量/高频）": {...},
    "DeepSeek R1（深度推理）": {...},
}
```

### 2.3 LiteLLM Proxy（可选）

所有模型可统一走 `http://localhost:4000/v1`，由 LiteLLM 做自动 fallback，详见 `litellm_config.example.yaml`。

---

## 三、Agent 决策流程

### 3.1 快捷路径（低延迟，不经过 LLM 决策）

```
用户输入
  → Orchestrator.detect_intent()       ← 纯关键词匹配
    ├── 命中（scan / processes / health / report / monitor 等）
    │     → 直接执行预设工具链（如 scan → query_security_scan_json）
    │     → 工具结果（~3000 字）+ advisor 骨架注入
    │     → LLM 仅负责总结 + 格式化回复
    │     → 返回带 data_summary 的完整回复
    └── 未命中（general / block）
          → 进入通用多轮路径
```

**优势**：减少 1-2 轮 LLM 调用，响应速度提升 40-60%。

### 3.2 通用多轮路径（灵活的 LLM 自主调用）

```
AgentBrain.chat(user_message)
  1. build_plan(user_message)          ← 意图识别
  2. search_knowledge(user_message)    ← 知识库 grounding
  3. format_plan_for_llm(plan)         ← 编排提示注入
  4. LLM 回复 → 含工具调用或直接回复
  5. 若含工具调用：
     a) 解析 tool_calls
     b) call_tool_local(name, args)    ← 本地执行，不走 MCP
     c) 工具结果注入对话历史
     d) 回到步骤 4（最多 10 轮）
  6. finish_reason != "tool_calls" → 返回最终回复
```

**关键设计**：
- 每轮工具结果截断至 2000 字符防止上下文过长
- 对话历史滑动窗口：保留最近 15 轮（纯内存，不写磁盘）
- 早期对话自动摘要压缩

### 3.3 自主任务路径（DeepSeek R1 驱动）

```
用户输入目标
  → AutonomousAgent → LLM (DeepSeek R1) 输出 JSON 步骤数组
    [
      {"type": "think", "content": "先检查系统负载"},
      {"type": "tool", "name": "get_system_health", "args": {}},
      {"type": "terminal", "command": "ps aux --sort=-%cpu | head -5"},
      {"type": "think", "content": "分析结果..."},
      ...
    ]
  → rules/engine 逐步校验（ALLOW / CONFIRM / DENY）
  → WorkflowEngine 逐条执行
  → 每步结果反馈给 LLM → LLM 可能动态调整后续步骤
  → 最终 LLM 总结汇报
```

---

## 四、工具架构

### 4.1 原始工具总览（23 个）

定义于 `security_agent/tools/registry.py`，注册到 `TOOL_REGISTRY` 全局字典。

| 类别 | 工具名 | 说明 |
|------|--------|------|
| **扫描** | `query_security_scan` | 人读格式安全扫描 |
| | `query_security_scan_json` | JSON 格式安全扫描 |
| | `run_full_security_check` | 综合体检（进程/端口/密码/敏感文件） |
| **进程** | `list_processes` | 列出系统进程 |
| | `get_process_detail` | 获取单个进程详情 |
| | `block_high_risk_process` | 拦截高危进程（需 CONFIRM） |
| **监控** | `start_monitor` | 启动 P2 实时监控 |
| | `stop_monitor` | 停止实时监控 |
| | `get_monitor_events` | 获取监控事件列表 |
| **网络** | `check_exposed_ports` | 检测 0.0.0.0 高危端口暴露 |
| | `list_network_connections` | 列出网络连接 |
| **终端** | `run_terminal_command` | 执行 shell 命令（白名单限制） |
| **知识** | `search_security_knowledge` | 搜索安全知识库 |
| | `get_grounded_advice` | 扫描 + 知识库 → 结构化建议 |
| | `build_knowledge_index` | 构建/更新向量检索索引 |
| **审计** | `get_audit_log` | 查询操作审计日志 |
| **报告** | `generate_security_report` | 生成 HTML 安全报告 |
| **健康** | `get_system_health` | 系统 CPU/内存/磁盘/网络状态 |
| **技能** | `run_autonomous_mission` | 运行自主任务（R1 驱动） |
| | `run_risk_demo` | 运行风险演练场景 |
| **其他** | 文件/路径检查等辅助工具 | — |

### 4.2 Skill 工具架构（26 个，5 个 Skill）

每个 Skill 遵循统一基类 `SkillBase`（`security_agent/skills/base.py`）：

```
SkillBase(ABC)
  ├── @property meta: SkillMeta      ← 元信息（名称/版本/标签）
  ├── get_tools() -> list[ToolDef]   ← 工具定义（name/description/parameters/handler）
  ├── get_playbooks() -> list[Playbook] ← 关联知识库条目
  ├── get_rules() -> list[str]       ← 注入 LLM system prompt 的运维规则
  ├── healthcheck() -> dict          ← Skill 自检
  └── on_alert(event) -> dict|None   ← 告警事件回调（升级策略引擎调用）
```

#### Skill 一览

| Skill | 工具数 | 核心工具 | 说明 |
|-------|--------|----------|------|
| **healthcheck** | 6 | `health_full_check`, `health_trend`, `health_threshold_check`, `health_disk_analysis`, `health_network_analysis`, `health_get_history` | CPU/内存/磁盘/网络监控、趋势分析、阈值告警 |
| **log_analyzer** | 6 | `log_scan`, `log_tail`, `log_search`, `log_patterns`, `log_recent_matches`, `log_incremental_scan` | 多源日志采集、10 种异常模式识别、增量扫描 |
| **security_hardening** | 5 | `hardening_ssh_audit`, `hardening_firewall_audit`, `hardening_vulnerability_scan`, `hardening_baseline_check`, `hardening_full_scan` | SSH 审计、防火墙审查、漏洞扫描、CIS 基线合规 |
| **config_manager** | 5 | `config_snapshot`, `config_diff`, `config_history`, `config_audit`, `config_add_watch` | 配置文件快照、变更检测 diff、版本追踪 |
| **incident_responder** | 4 | `incident_diagnose`, `incident_self_heal`, `incident_list_scripts`, `incident_response_plan` | 根因分析决策树、自愈脚本、处置流程编排 |

#### 注册机制

```
skills/registry.py
  → 自动遍历 skills/ 下所有子目录
  → 实例化每个 Skill（懒加载）
  → get_tools() → 合并到 TOOL_REGISTRY
  → 首次调用 AgentBrain.chat() 时自动发现注册
```

---

## 五、安全引擎

### 5.1 规则引擎（`security_agent/rules/engine.py`）

终审控制，用于 `run_terminal_command` 和 `block_high_risk_process`：

```
规则评估 → 返回 Decision:
  ALLOW      — 允许执行
  CONFIRM    — 需用户界面确认（杀进程、root 写操作）
  DENY       — 禁止执行

判断依据：
  ├─ 高危进程名检测（nc / nmap / hydra / sqlmap / metasploit …）
  ├─ 高危命令模式（rm -rf /, chmod 777, fork bomb, dd if=…）
  ├─ 只读命令豁免（grep / cat / tail / awk / sed 等 → 允许）
  └─ 演练场景豁免（安全诱饵路径 → 放行）
```

### 5.2 扫描引擎（`security_agent/scanner/engine.py`）

```
run_security_scan()
  1. 进程列表采集（ps aux / wmic）
  2. 风险检测：
     - 高危工具名匹配（白名单过滤系统进程）
     - 敏感命令行模式
  3. 敏感路径检测（/etc/shadow, SSH 密钥等）
  4. 网络端口暴露检测（0.0.0.0 高危端口）
  5. 密码/密钥泄露扫描（.env 等）
  6. HTML 报告生成
```

**高危进程白名单**：`sync`, `systemd`, `sshd`, `nginx`, `docker`, `bash`, `python` 等 30+ 系统进程不会被误报。

**高危端口集合**（`EXPOSED_RISKY_PORTS`）：23(Telnet)、445(SMB)、3306(MySQL)、3389(RDP)、5432(PG)、6379(Redis)、27017(MongoDB) 等 18 个。

### 5.3 终端执行器（`security_agent/terminal/executor.py`）

```
run_terminal_command(command, timeout=30)
  ├─ 白名单命令路径限制（/usr/bin/, /bin/, /snap/bin/ 等）
  ├─ 高危命令模式过滤（与规则引擎联动）
  ├─ 只读命令前缀豁免
  ├─ 超时控制（默认 30 秒）
  ├─ 输出截断（最多 10000 字符）
  └─ 密钥自动打码（redact）
```

---

## 六、实时监控（P2 监控）

### 6.1 监控循环

`security_agent/monitor/service.py` — 约 5 秒一轮巡检：

```
MonitorService.loop()
  ├── 进程快照采集
  │     └─ 敏感路径检查（/etc/shadow, /root/.ssh/...）
  ├── 登录审计（auth.log / secure）
  │     ├─ 解析最近 100 条日志行
  │     └─ 检测登录失败暴破（阈值：默认 5 次/session）
  ├── 监听端口 diff
  │     ├─ ss -tlnp → 解析监听端口列表
  │     └─ 对比上次快照 → 新端口/关闭端口告警
  ├── cron 文件 hash diff
  │     └─ 检测 cron 文件变更（被篡改风险）
  └── CPU 阈值检查
        └─ CPU > 阈值 → 告警
```

### 6.2 告警升级策略

所有监控事件通过 `EscalationEngine` 分级处理：

```
监控事件 → EscalationEngine.process_event()
  ├── IGNORE               → 忽略（心跳、新进程等信息级事件）
  ├── NOTIFY_ONLY          → 仅通知（记录 + 桌面弹窗）
  ├── NOTIFY_AND_SUGGEST   → 通知 + 调用所有 Skill 的 on_alert() 诊断
  │                           → 汇总诊断建议（需人工确认执行）
  └── AUTO_FIX             → 自动修复
                              → 仅限低风险操作（清理 /tmp、日志轮转）
```

**升级流程**：

1. 监控事件 → `_push()` → `EscalationEngine.process_event()`
2. 按 `ESCALATION_RULES` 确定级别和动作
3. 路由到所有注册 Skill 的 `on_alert()` 回调
4. 汇总 Skill 返回 → 生成告警摘要
5. 低风险自动修复 / 高风险通知人工

---

## 七、知识检索与防幻觉

### 7.1 混合检索

```
用户问题
  → hybrid 检索（关键词 + 可选向量 embedding）
  → 返回 top-k 匹配条目（含知识库编号 PB-*）
  → 注入 LLM system prompt 或 user message 开头
  → 工具获取实时数据（扫描/端口/进程）
  → advisor 输出结构化建议
```

**向量检索**（可选，由 `RAG_USE_EMBEDDINGS` 控制）：
- 默认使用 `text-embedding-3-small`
- 构建索引后支持语义相似度匹配

**关键词检索**（始终启用）：
- 基于文件内容全文搜索
- 匹配剧本标签、描述、修复步骤等字段

### 7.2 防幻觉约束

```
AgentBrain system prompt 显式要求：
  ✅ 必须引用知识库编号（PB-*）或工具输出
  ❌ 禁止编造 PID / 端口 / 扫描结果
  ✅ 不确定时先调工具再回答

advisor 输出结构：
  ┌─ 结论（结论前置）
  ├─ 步骤（如何修复/处理）
  └─ 请勿（不要做什么）
```

---

## 八、风险演练系统

| 模块 | 路径 | 说明 |
|------|------|------|
| **场景** | `security_agent/demo/scenarios.py` | 11 个预定义安全演练场景 |
| **校准** | `security_agent/demo/evaluator.py` | 101 个自动化测试用例（66 检测 + 35 终端） |
| **边界** | `security_agent/demo/boundary.py` | 系统边界感知测试 |
| **诱饵** | `security_agent/demo/decoy.py` | 模拟高危进程/行为，用于测试检测逻辑 |
| **服务** | `security_agent/demo/service.py` | 演练服务编排 |

**使用方式**：
- UI「风险演练」页面：场景选择、校准库浏览、边界测试、立体图展示
- CLI：`uv run python scripts/demo_risk.py calibration`
- 改检测逻辑后运行校准验证：`uv run python scripts/demo_risk.py calibration`

---

## 九、部署架构

### 9.1 启动与停止

| 脚本 | 作用 |
|------|------|
| `boot_start.sh` | 安装依赖、加载 `.env`、后台启动 Streamlit（`127.0.0.1:8501`） |
| `boot_stop.sh` | 停止控制台、释放 8501 端口 |
| `打开应用.sh` | 麒麟桌面双击启动（防闪退） |
| `open-app.sh` | 通用桌面快捷启动 |

### 9.2 数据目录结构

```
data/
├── alerts/                  # 告警持久化
│   ├── alerts.log           # 告警文本日志
│   ├── events.jsonl         # 告警事件 JSONL
│   ├── latest.json          # 最新告警摘要
│   └── unread.count         # 未读告警数
├── patrol_reports/          # 定时巡检报告（JSON）
│   ├── healthcheck_latest.json
│   └── *_latest.json        # 各类型最新报告
├── config_snapshots/        # 配置文件快照
│   ├── *.content            # 文件内容快照
│   ├── latest.json          # 最新快照索引
│   └── snapshot_*.json      # 时间戳快照
└── audit.log                # 操作审计日志
```

### 9.3 定时巡检（Cron）

```bash
*/30 * * * *  cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py healthcheck
*/15 * * * *  cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py log_scan
0 * * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py config_diff
0 */6 * * *   cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py hardening
0 2 * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py daily_report
0 6 * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py full
```

---

## 十. 配置体系（`.env`）

| 变量 | 含义 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 对话模型密钥/接口/模型 | `mimo-v2.5-pro` |
| `AUTONOMOUS_API_KEY` / `AUTONOMOUS_MODEL` | 自主规划模型 | `deepseek-reasoner` |
| `BUDGET_API_KEY` / `BUDGET_MODEL` | 批量任务模型 | `deepseek-chat` |
| `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` | 向量嵌入 | `text-embedding-3-small` |
| `RAG_USE_EMBEDDINGS` | 是否建向量索引 | `true` |
| `MONITOR_AUTH_ENABLED` / `MONITOR_LISTEN_ENABLED` / `MONITOR_CRON_ENABLED` | P2 监控开关 | `true` |
| `AUTH_FAIL_BURST_THRESHOLD` | 登录失败暴破阈值 | `5` |
| `NOTIFY_DESKTOP` | 桌面通知开关 | `true` |
| `SECURITY_AGENT_PYTHON` | Python 解释器路径 | `sys.executable` |

---

## 十一. 关键设计特点

1. **多模型路由** — 不同任务走不同 LLM，旗舰模型用于对话，R1 用于深度规划，V3.2 用于批量生成，平衡成本与能力
2. **双重工具路径** — 快捷路径（低延迟、不经 LLM 决策）vs 通用路径（灵活多轮、LLM 自主选工具）
3. **Skill 插件化** — 5 个 Skill 通过统一 `SkillBase` 接口注册，无需修改核心代码即可扩展新能力
4. **自动化分级** — 四级告警升级策略（IGNORE → NOTIFY_ONLY → NOTIFY_AND_SUGGEST → AUTO_FIX）
5. **防幻觉体系** — 知识库 grounding + 实时工具数据 + 结构化 advisor + LLM prompt 约束，四层保障
6. **非专业用户友好** — 终端命令执行结果自动生成白话摘要（`_summarize_terminal_output`）；提到任何进程名时附带一句话说明该进程用途
7. **国产系统适配** — 自动识别银河麒麟（Kylin）、统信 UOS 等国产操作系统，适配文件路径和命令行

---

## 十二. 关键依赖

| 包 | 用途 |
|----|------|
| `streamlit` | Web UI 框架 |
| `openai` | LLM API 客户端 |
| `python-dotenv` | 环境变量加载 |
| `jinja2` / `weasyprint` | HTML 报告生成 |
| `pydantic` | 数据模型验证 |
| `httpx` | 异步 HTTP 客户端 |
| `watchdog` | 文件系统监控（配置快照） |
| `platformdirs` | 跨平台目录路径 |
| `litellm`（可选） | 统一 LLM 路由代理 |

---

> 本文档由项目源码自动分析生成，随项目版本迭代更新。
> 最近更新：v0.6.0
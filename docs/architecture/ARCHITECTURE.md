# 架构 v0.8.0（已归并）

> ⚠️ **本文档已归并至终版权威论述** → **[FINAL_ARCHITECTURE.md](FINAL_ARCHITECTURE.md)**  
> 本文保留用于 Streamlit 九页 UI 细节参考，架构定义以 FINAL_ARCHITECTURE.md 为准。

## 部署入口

| 脚本 / 命令 | 作用 |
|-------------|------|
| `boot_start.sh` | Streamlit 控制台 `127.0.0.1:8501` |
| `boot_stop.sh` | 停止 Streamlit |
| `uv run uvicorn security_agent.api.app:app --port 8000` | FastAPI 后端（Vue 对接） |
| `cd frontend && npm run dev` | Vue 开发服务器 `:5173` |

## 应用分层（五层流水线摘要）

```text
用户输入 → L1 感知计划 → L2 安全管控(+沙箱) → L3 推理分发 → L4 审计回流 → L5 数学分析
           不执行           不执行              MCP+Flow        trace+Wiki      指标+绘图

表现层: Streamlit | Vue3(计划/执行双模式) | MCP Client
API层:  FastAPI — L1–L5 分路由 + 执行闸门
L3:     MCP 工具 + 封装流程（metrics/logs/repair/schedule · 单一职责）
知识:   Gitee Wiki（边界对抗 · 规范库 · 回流案例）
```

详见 [FIVE_LAYER_PIPELINE.md](FIVE_LAYER_PIPELINE.md)。

## 应用分层（模块细节 · 历史）

## Skill 架构（v0.6.0 新增）

```text
security_agent/skills/
    ├── base.py              SkillBase 抽象基类 + ToolDef / SkillMeta
    ├── registry.py          Skill 注册中心（自动发现 + 工具合并 + 告警路由）
    ├── healthcheck/         健康巡检 Skill（6 工具）
    ├── log_analyzer/        日志分析 Skill（6 工具）
    ├── security_hardening/  安全加固 Skill（5 工具）
    ├── config_manager/      配置管理 Skill（5 工具）
    └── incident_responder/  故障响应 Skill（4 工具）

每个 Skill 提供:
  - get_tools()        → 工具列表（自动合并到 TOOL_REGISTRY）
  - get_playbooks()    → 关联知识库条目
  - get_rules()        → 运维规则（注入 LLM system prompt）
  - healthcheck()      → Skill 自检
  - on_alert()         → 告警事件回调（升级策略引擎调用）
```

### Skill 工具总览

| Skill | 工具 | 说明 |
|-------|------|------|
| **healthcheck** | health_full_check, health_trend, health_threshold_check, health_disk_analysis, health_network_analysis, health_get_history | CPU/内存/磁盘/网络监控、趋势分析、阈值告警 |
| **log_analyzer** | log_scan, log_tail, log_search, log_patterns, log_recent_matches, log_incremental_scan | 多源日志采集、10 种异常模式识别、增量扫描 |
| **security_hardening** | hardening_ssh_audit, hardening_firewall_audit, hardening_vulnerability_scan, hardening_baseline_check, hardening_full_scan | SSH 审计、防火墙审查、漏洞扫描、CIS 基线合规 |
| **config_manager** | config_snapshot, config_diff, config_history, config_audit, config_add_watch | 配置文件快照、变更检测 diff、版本追踪 |
| **incident_responder** | incident_diagnose, incident_self_heal, incident_list_scripts, incident_response_plan | 根因分析决策树、自愈脚本、处置流程编排 |

## 告警升级策略（v0.6.0 新增）

```text
监控事件 → EscalationEngine
  ├── IGNORE          → 忽略（心跳、新进程等信息级）
  ├── NOTIFY_ONLY     → 仅通知（记录 + 桌面弹窗）
  ├── NOTIFY_AND_SUGGEST → 通知 + Skill 诊断建议（需人工确认执行）
  └── AUTO_FIX        → 自动修复（仅低风险：清理 /tmp、日志轮转）

升级流程:
  1. 监控事件 → _push() → EscalationEngine.process_event()
  2. 按 ESCALATION_RULES 确定级别和动作
  3. 路由到所有 Skill 的 on_alert() 回调
  4. 汇总 Skill 返回 → 生成摘要
  5. 低风险自动修复 / 高风险通知人工
```

## 定时巡检（v0.6.0 新增）

```bash
# Cron 配置示例
*/30 * * * *  cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py healthcheck
*/15 * * * *  cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py log_scan
0 * * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py config_diff
0 */6 * * *   cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py hardening
0 2 * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py daily_report
0 6 * * *     cd /home/oy0/security-agent && uv run python scripts/scheduled_patrol.py full
```

报告输出到 `data/patrol_reports/`，支持 `*_latest.json` 快捷读取。

## 多模型路由（v0.6.0 更新）

```text
侧栏模型切换器
    ├── mimo-chat     → MiMo v2.5 Pro（默认，旗舰 agent + 工具调用）
    ├── mimo-fast     → MiMo v2.5（快速轻量）
    ├── deepseek-reasoner → DeepSeek v4-pro（深度规划/推理）
    └── deepseek-chat     → DeepSeek v4-flash（性价比高频任务）

AgentBrain / LLMClient
    ├── 直接调用各模型 API（当前主路径）
    └── 可选：通过 LiteLLM Proxy 统一路由 + 自动 fallback
```

**当前部署状态**：
- **主路径**：应用层直接调用 MiMo / DeepSeek 官方 API，内置 client-side fallback（MiMo 失败自动切 DeepSeek）。
- **LiteLLM Proxy**：配置已就绪（`litellm_config.yaml`），支持统一入口 + 成本追踪 + fallback。
  - **本地部署受限**：银河麒麟 + KYSEC 安全策略阻止 `uvloop` 原生编译（libuv make 权限不足），Docker 守护进程权限受限。
  - **推荐**：在支持 Docker 的生产环境使用 `bash scripts/litellm_docker.sh start` 部署。

| 模型别名（UI） | 实际后端模型 | 场景 | 备注 |
|----------------|--------------|------|------|
| mimo-chat | openai/mimo-v2.5-pro | Agent 对话、工具调用、安全分析 | 默认首选 |
| mimo-fast | openai/mimo-v2.5 | 快速问答 | 轻量任务 |
| deepseek-reasoner | deepseek/deepseek-v4-pro | 自主规划、深度推理 | 高质量决策 |
| deepseek-chat | deepseek/deepseek-v4-flash | 批量/高频任务 | 性价比之选 |
| text-embedding-3-small | openai/text-embedding-3-small | RAG 向量检索 | 占位 Key（未启用时不调用） |

**LiteLLM 配置要点**（`litellm_config.yaml`）：
- 使用真实模型 ID（v4-pro / v4-flash）而非旧版 reasoner/chat 名称。
- Fallback 链：mimo-chat → deepseek-chat。
- 启动命令：`uv run litellm --config litellm_config.yaml --port 4000`（或 Docker）。

## 智能检索与防幻觉

```text
用户问题
  → hybrid 检索（关键词 + 可选向量）
  → 注入 PB-* 知识条目（含 Skill 关联的 HB-*/HI-* 条目）
  → 工具实盘（scan / 端口 / 进程 / Skill 工具）
  → advisor 输出（含是否需用户确认）
```

| 能力 | 说明 |
|------|------|
| `search_security_knowledge` | 按威胁标签检索剧本 |
| `get_grounded_advice` | 扫描 + 知识库 → 结构化建议 |
| `check_exposed_ports` | 0.0.0.0 高危端口 |
| `build_knowledge_index` | 可选向量索引 |
| root 规则 | `sudo` 写 → NEED_CONFIRM；只读 `sudo systemctl status` 允许 |

## P2 监控与脱敏

```text
MonitorService（约 5s）
  ├─ 进程 / 敏感路径
  ├─ auth.log | secure → 登录失败、暴破
  ├─ 监听端口 diff
  ├─ cron 文件 hash diff
  └─ CPU 阈值检查 → 告警 → EscalationEngine → Skill on_alert

redact → 审计 / 终端 / 工具输出 / UI
```

## 风险演练

| 入口 | 说明 |
|------|------|
| UI「风险演练」 | 场景、校准库、边界、立体图 |
| `scripts/demo_risk.py` | CLI |
| 校准 | 66 检测 + 35 终端 = **101 用例** |

改检测逻辑后：`uv run python scripts/demo_risk.py calibration`

## 自主任务流程

1. 用户输入目标  
2. LLM 输出 JSON 步骤（tool / terminal / think）  
3. 规则引擎逐步校验  
4. WorkflowEngine 执行  
5. LLM 总结  

## 对话路径

UI → AgentBrain → LLM API → `call_tool_local`（默认不走 MCP，低延迟）

首次调用时自动发现并注册 Skill 工具到 TOOL_REGISTRY（懒加载）。

## MCP（可选）

```bash
uv run python cli.py --mcp
```

## 配置（`.env`）

| 变量 | 含义 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | 对话模型密钥 | — |
| `LLM_BASE_URL` / `LLM_MODEL` | 对话模型接口 | `mimo-v2.5-pro` |
| `BUDGET_API_KEY` / `BUDGET_MODEL` | 批量任务模型 | `deepseek-chat` |
| `AUTONOMOUS_API_KEY` / `AUTONOMOUS_MODEL` | 自主规划模型 | `deepseek-reasoner` |
| `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` | 向量嵌入 | `text-embedding-3-small` |
| `RAG_USE_EMBEDDINGS` | 是否建向量索引 | `true` |
| `MONITOR_*_ENABLED` | P2 监控开关 | `true` |
| `HEALTH_*_WARN` / `HEALTH_*_CRITICAL` | 健康巡检阈值 | 见 healthcheck/skill.py |
| `NOTIFY_DESKTOP` | 桌面通知开关 | `true` |

> **LiteLLM Proxy（可选）**：部署后把所有 `BASE_URL` 改为 `http://localhost:4000/v1`，详见 `litellm_config.example.yaml`。
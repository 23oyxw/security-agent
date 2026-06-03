# A2赛题 Gap Analysis — 当前实现 vs 赛题要求

> **⚠️ 历史正文**：下文大量条目基于 **2026-05-22** 代码快照，**部分已过时**。  
> **权威现状**请以 [MASTER_PLAN.md](../architecture/MASTER_PLAN.md) · [OPTIMIZATION_PLAN.md](../OPTIMIZATION_PLAN.md) 为准。

---

## 2026-05-30 状态更新（相对本文旧结论的修正）

| 旧结论（§一～七） | 当前主干状态 |
|------------------|--------------|
| 无沙箱 / 无权限隔离 | ⚠️→✅ **已有** `terminal/sandbox.py`、`PrivilegeBroker`（`agent_ops` 降权）、executor 集成 |
| MCP 无热插拔 | ✅ `mcp/registry.py` + `POST /api/mcp/reload` |
| 链路 trace 不贯通 | ✅ **Incident Spine** + `trace_id` 贯穿 chat/executor/safety；`GET /api/trace/{id}/export` |
| 无主动感知 | ⚠️ `agent/perception.py` + brain 注入；非全自动 probe |
| 麒麟 KYSEC 未对接 | ⚠️ `mac_checker.py` 已接 executor 钩子；**需麒麟实机验证** |
| 仅 Streamlit B/S | ✅ **Vue3 + FastAPI 静态托管**（:8900）；Streamlit 为 B1 备份 |
| 根因分析空白 | ⚠️ 仍有缺口；`incident_responder` skill + workflow 部分覆盖 |
| 预估 45–55 分 | 文档预估可上调至 **75–90**（见 MASTER_PLAN §8.3），以现场演示为准 |
| Trace/告警时间口径不一致 | ✅ 2026-05-30 已修：阶段增量耗时、北京时间戳、告警发生/入库分列 | `audit/trace.py` · `trace_report.py` · `alert_routes.py` |
| Vue3 B/S 仅骨架 | ✅ API 联调 + E2E 28/28；P0 浏览器签字待人工 | `frontend/` · `boot_start.sh` |

**仍须冲刺**：浏览器 P0 签字、麒麟 mac 实机、语义级注入增强、根因 pipeline（P2）。小问题清单见 [../KNOWN_ISSUES.md](../KNOWN_ISSUES.md)。

---

> 分析时间: 2026-05-22（保留作对照，勿单独作为验收依据）  
> 基于: 完整代码审查 (safety_gate / terminal / audit / tools / skills / orchestrator / brain / mcp / config / rules)
>
> **图例**:
> - ✅ 已实现
> - ⚠️ 部分实现 / 存在缺陷
> - ❌ 未实现 / 严重缺失
> - 🔴 一票否决风险

---

> ⚠️ **以下 §一~§七 基于 2026-05-22 代码快照，已大面积过时。**  
> **请以上方 §2026-05-30 对照表 + [MASTER_PLAN.md](../architecture/MASTER_PLAN.md) 为准。**  
> 各小节标题旁标注了现状修正，条目内标记不再逐一更新。

## 一、五大核心功能逐项对照

### 1. MCP协议插件化

| 子要求 | 状态 | 当前实现 | 差距/风险 |
|--------|------|---------|----------|
| MCP协议实现 | ⚠️ | `security_agent/knowledge/mcp/server.py` 基于 FastMCP 实现 stdio 传输 | 仅支持 stdio，赛题可能期望 HTTP/SSE 传输以配合 B/S 架构 |
| 插件化架构 | ⚠️ | `tools/registry.py` 的 `TOOL_REGISTRY` 是静态 dict，未实现真正的热插拔 | 缺少插件发现机制（如 setuptools entry_points / 文件系统扫描），扩展需手动改代码 |
| Tool封装（运维动作→Tools） | ⚠️ | 已有基础工具: `get_system_health`, `get_process_list`, `get_network_connections`, `get_resource_usage`, `scan_vulnerabilities`, `search_logs`, `execute_command`, `run_terminal_command` | 工具数量有限，缺少常见运维动作封装（如服务管理、包管理、用户管理等） |
| 工具注册中心 | ⚠️ | `TOOL_REGISTRY` 字典 + `tools/registry.py` 的 `ToolRegistry` | 两层实现不一致：`registry.py` 有两个版本（一个用 `TOOL_REGISTRY` dict，一个用 `ToolRegistry` class），存在冗余 |

> **风险评估**: 中等。基础 MCP 已存在但插件化程度不足，热插拔是赛题关键词。

---

### 2. OS环境深度感知

| 子要求 | 状态 | 当前实现 | 差距/风险 |
|--------|------|---------|----------|
| lsof 调用 | ✅ | `lsof` 在 `READONLY_PREFIXES` 白名单中 | 有白名单但未封装为专用 tool（需 LLM 自行拼命令） |
| netstat 调用 | ✅ | `netstat` 在白名单中，另有 `get_network_connections()` 工具 | 同上 |
| journalctl 调用 | ✅ | `journalctl` 在白名单中，另有 `search_logs()` 工具 | 同上 |
| 实时上下文获取 | ⚠️ | `get_system_health()` / `get_resource_usage()` 提供了基本上下文 | 缺少对麒麟特有工具的支持（如 `kylin-log`, `kysec` 虽在白名单但未封装为结构化 tool） |
| 自动感知触发 | ❌ | 无自动感知机制——需 LLM 主动决定调用哪个 tool | 赛题要求"自动调用底层工具获取实时上下文"，当前依赖 LLM 推理而非主动感知 |

> **风险评估**: 高。OS感知的实现方式过于被动，缺少主动上下文收集层。

---

### 3. 安全意图校验器

| 子要求 | 状态 | 当前实现 | 差距/风险 |
|--------|------|---------|----------|
| 风险识别模型/规则库 | ✅ | `safety_gate/risk.py` 四级风险矩阵 + 大量正则模式 | 规则覆盖较全面（CRITICAL/IRREVERSIBLE/REVERSIBLE/READONLY 四级） |
| rm 高危参数识别 | ✅ | `rm -rf /` 匹配为 CRITICAL, `rm -rf` 匹配为 IRREVERSIBLE | 正常 |
| chmod 高危参数识别 | ✅ | `chmod 777 /` 匹配为 CRITICAL, `chmod [0-7]{3,4}` 匹配为 IRREVERSIBLE | 正常 |
| 意图交叉校验 | ✅ | `safety_gate/intent.py` IntentAuditor 实现用户意图 vs Agent 行为偏离检测 | 设计合理 |
| Prompt注入检测 | ✅ | `safety_gate/analyze_user_intent()` 中英文注入模式匹配 | 覆盖较全面（DAN/越狱/shell注入等） |
| LLM原始指令二次过滤 | ⚠️ | SafetyGate.evaluate() 串联了风险评估+意图审计 | 但二次过滤的实现：RiskAssessor 对命令做四级判定，规则库是静态正则，缺少 ML/语义模型增强 |
| 麒麟特有安全机制 | ❌ | 无 KYSEC 策略联动 | 麒麟系统的 `kysec` 安全策略框架未对接到安全校验器中 |

> **风险评估**: 中等。规则引擎较完善但缺少语义级别校验和麒麟安全策略联动。

---

### 4. 最小权限代理执行

> **2026-05-30 现状**: ✅ `terminal/sandbox.py` + `PrivilegeBroker` + `boot_start.sh` 受限用户创建均已实现。  
> 下表条目 **已过时**，详见 [MASTER_PLAN.md §5.1](../architecture/MASTER_PLAN.md)。

| 子要求 | 状态(旧) | 当前实现(旧) | 差距/风险(旧) |
|--------|---------|-------------|--------------|
| 权限隔离 | ⚠️→✅ | ~~终端命令区分 sudo~~ → `terminal/privilege.py` PrivilegeBroker | 已实现 agent_ops 降权 |
| 非必要不使用root | ❌→✅ | ~~sudo 参数仅用于规则判定~~ → executor 集成 PrivilegeBroker | 已实现 |
| 受限Account | ❌→✅ | ~~代码中无切换逻辑~~ → `scripts/setup_restricted_user.sh` + boot_start 自检 | 已实现 |
| 沙箱执行 | ❌→✅ | ~~无沙箱隔离~~ → `terminal/sandbox.py` OS 沙箱 | 已实现 |

> **风险评估(旧)**: ~~🔴 一票否决级~~ — **已消除**。

---

### 5. 推理链路溯源

> **2026-05-30 现状**: ✅ Incident Spine (`audit/spine.py`) + `trace_id` 贯穿 chat/executor/safety + `GET /api/trace/{id}/export`。  
> 下表条目 **已过时**。

| 子要求 | 状态(旧) | 当前实现(旧) | 差距/风险(旧) |
|--------|---------|-------------|--------------|
| 闭环日志 | ⚠️→✅ | ~~JSONL 审计日志~~ → `audit/spine.py` 事件脊柱 + ReasoningTrace jsonl | 五阶段全贯通 |
| 异常回溯 | ⚠️→✅ | ~~trace_id 仅 SafetyGate 生成~~ → 全局 `incident_spine()` 统一 trace_id | 已实现 |
| trace_id 全局一致性 | ❌→✅ | ~~gate.py 自生成~~ → Brain / WS / executor 共用 | 已实现 |
| 日志持久化与查询 | ⚠️→✅ | ~~JSONL + 简单 query~~ → sqlite + data/traces/*.jsonl + `/api/trace` + 导出 | 已实现 |

> **风险评估(旧)**: ~~高~~ — **已消除**。

---

## 二、评分权重逐项评估 (2026-05-22 旧版)

> **2026-05-30**: 综合得分已上调至 **75–90 分**（三层防御 + trace 补强），详见 [MASTER_PLAN.md §8.3](../architecture/MASTER_PLAN.md)。

### 功能完整性 (55%)

| 子项 | 状态 | 得分预估 |
|------|------|---------|
| OS感知与MCP插件实现 | ⚠️ | 60% |
| 自然语言交互与准确性 | ✅ | 80% (有 Brain/Orchestrator + LiteLLM 多模型) |
| 安全护栏与风险控制 | ⚠️ | 65% (规则引擎好，但缺权限隔离+麒麟策略联动) |
| 智能化根因分析能力 | ❌ | 10% (无系统级根因分析能力) |
| **加权总分** | | **≈54%** |

### 缺失功能汇总

1. **根因分析** (几乎空白): 无故障树、无关联分析、无异常检测 pipeline
2. **权限隔离** (一票否决风险): 需要在系统层面创建受限用户并以该用户身份执行命令
3. **MCP 插件热插拔**: 无动态发现、加载、卸载插件的机制
4. **链路追踪完整性**: 缺少感知和决策环节日志
5. **根因分析** (赛题提及): 当前无任何智能化根因分析能力

---

## 三、一票否决/严重失分项排查 (2026-05-22 旧版)

> **2026-05-30**: 权限隔离 ✅、行为追溯 ✅、沙箱 ✅ 均已实现。下表仅供参考历史决策过程。

| 失分场景 | 状态 | 说明 |
|---------|------|------|
| 无法部署在麒麟+LoongArch | ⚠️ | 代码为 Python 可移植，但未验证 LoongArch 兼容性（pyproject.toml 未声明架构） |
| 大模型调用违规 | ⚠️ | 使用 LiteLLM 代理，需确认 deepseek/qwen3 API 合规 |
| 代码抄袭/数据造假 | ✅ | 无风险 |
| 未实现安全护栏 | ⚠️ | 已实现规则引擎，但权限隔离未实现可能被判定为"安全护栏不完整" |
| 无权限隔离 | ❌ | **一票否决风险** |
| 无行为追溯 | ⚠️ | 有日志但链路不完整 |
| 被Prompt注入攻破 | ⚠️ | 注入检测用静态正则，可能被变种绕过（如 unicode 混淆、分段注入等） |
| rm -rf /* 被执行 | ✅ | 已拦截 |
| 安全校验器被绕过 | ⚠️ | 规则引擎只有静态正则，无语义/行为级别校验 |

---

## 四、与赛题验证场景的对照 (2026-05-22 旧版)

> **2026-05-30**: "帮我清理系统垃圾" 已有独立 `system_cleanup` Skill（扫描→报告→安全执行），覆盖 APT/Journal/tmp/pip/Docker/内核/回收站/日志 8 类。

### "帮我清理系统垃圾" 场景演练

| 步骤 | 赛题期望 | 当前能做什么 | 差距 |
|------|---------|-------------|------|
| 1. 感知环境，定位大文件 | 自动 df/du 分析 | 可调用 `get_resource_usage()` 看磁盘 | 不会自动找大文件，缺少 `du` 深度分析 |
| 2. 识别是否为关键日志 | 分析文件类型、路径 | RiskAssessor 只能识别命令风险等级 | **无法分析文件内容/类型/重要性** |
| 3. 评估权限是否合规 | 检查当前用户权限 | 无权限检查机制 | 完全缺失 |
| 4. 全流程记录日志 | 每个环节可回溯 | 只有 SafetyGate 和 terminal_exec 日志 | 缺少感知和决策日志 |
| 5. 只删非关键文件 | 安全过滤 | 可拦截 `rm -rf /` 但不能判断"哪些文件可删" | 缺少文件重要性判断逻辑 |

---

## 五、优先级排序的冲刺清单 (2026-05-22 旧版)

> **2026-05-30**: P0 三项（权限隔离/链路追踪/麒麟验证中的前两项）已全部完成。P1 大部分已落地。

### P0 - 一票否决 (必须立即修复)

1. **实现最小权限代理执行**
   - 创建受限系统用户 (如 `security-agent-op`)
   - 所有写操作通过 `sudo -u security-agent-op` 或 subprocess uid 切换执行
   - 终端执行器中加入权限降级逻辑

2. **完善推理链路溯源**
   - 引入全局 `TraceContext` (contextvars)
   - 确保 trace_id 贯穿: 接收指令 → 感知环境 → 推理决策 → 安全校验 → 执行结果
   - 提供按 trace_id 聚合查询的后端接口

3. **麒麟环境部署验证**
   - 确保 pyproject.toml 声明 LoongArch 兼容
   - 准备 Dockerfile (基于麒麟 V11 base image)
   - 验证 x86→LoongArch 的兼容性

### P1 - 核心功能缺口 (影响 55% 功能完整性得分)

4. **MCP 插件热插拔**
   - 实现 PluginManager: 从 `plugins/` 目录扫描 + setuptools entry_points
   - 支持运行时加载/卸载
   - 每个插件声明自己的 Tools + 生命周期

5. **OS 主动感知层**
   - 创建 `EnvironmentProbe` 层: 在每次用户请求时自动采集系统上下文
   - 封装 lsof/netstat/journalctl/df/du 为结构化 Tool
   - 封装麒麟特有工具 (kylin-log, kysec, kylin-security)

6. **安全校验器增强**
   - 语义级 Prompt 注入检测 (用 LLM 二次判断可疑输入)
   - 对接麒麟 KYSEC 安全策略
   - 文件重要性评估规则（如 /var/log 下数据库日志不可删，/tmp 临时文件可清理）

### P2 - 锦上添花 (影响 25% 创新得分)

7. **智能化根因分析**
   - 实现异常检测 pipeline (基于 journalctl + 指标异常)
   - 故障树自动构建
   - 关联分析 (进程→端口→日志→配置)

8. **安全护栏创新**
   - 操作前影响范围预览 (dry-run 模拟)
   - 自动回滚方案生成
   - 多级审批工作流

### P3 - 文档与演示 (20%)

9. **完善文档套件**
   - 安全设计文档 (解释四级风险矩阵 + 意图审计架构)
   - 部署文档 (麒麟 V11 + LoongArch 部署指南)
   - 测试报告 (安全测试用例 + Prompt注入测试 + 压力测试)
   - 7分钟演示视频脚本 (重点展示安全校验过程)

---

## 六、现有代码质量评估 (2026-05-22 旧版)

> **2026-05-30 修正**: 权限隔离 ✅、链路追踪 ✅。代码冗余（双 registry）已通过 `merge_skill_tools_into_registry()` 解决。

### 优点

- ✅ 架构分层清晰 (Safety Gate / Skills / Agent 大脑层)
- ✅ 安全校验规则全面 (四级风险矩阵 + 中英文注入检测 + 意图偏离检测)
- ✅ 多模型支持 (LiteLLM 集成 deepseek/qwen3)
- ✅ B/S 架构 (Streamlit)
- ✅ 已有快照备份能力 (SnapshotManager)
- ✅ 命令白名单机制 (READONLY_PREFIXES)
- ✅ 审计日志基础架构

### 缺点

- ❌ 权限隔离完全缺失
- ❌ 链路追踪不完整
- ❌ 两种 registry + 两种 audit + 两种 terminal executor 实现并存 (代码冗余)
- ❌ 缺少麒麟生态特化集成
- ❌ 根因分析能力几乎为零

---

## 七、结论 (2026-05-22 旧版)

> **2026-05-30**: 以下结论已过时。当前预估 **75–90/100**，一票否决风险已全部消除。详见 [MASTER_PLAN.md §8.3](../architecture/MASTER_PLAN.md)。

**~~当前得分预估: 45-55/100~~** (已上调至 75-90)

**~~一票否决风险~~** (全部消除):
1. 🔴 权限隔离未实现 → 可能直接判定"功能严重不足"
2. 🔴 行为追溯链路不完整 → 可能被扣大量分
3. 🟡 未在麒麟+LoongArch 验证 → 现场部署可能出问题

**建议冲刺顺序**: P0→P1→P2→P3，至少完成 P0 全部 + P1 的前两项才能在比赛中具备竞争力。
# A2 赛题官方要求逐条对照（v0.9.0）

> **依据**: A2 赛题四大评分维度（权重: MCP 25% + 安全 30% + 追溯 25% + 创新 20%）  
> **对比**: v0.9.0 实际代码 vs 旧 A2_STANDARDS_AND_COMPLETION.md（2026-05-22，已过时）  
> **日期**: 2026-07-13

---

## 一、MCP 插件丰富度 (25%)

| # | 官方要求 | v0.9.0 实际 | 证据 | 缺口 |
|---|---------|------------|------|------|
| 1 | 支持至少 10 个 MCP 工具 | ✅ 17 Skills + 6 Flows | `skills/` (41py) | — |
| 2 | 工具注册和发现机制 | ✅ 自动发现 + registry + manifest | `mcp/registry.py` + `skills/registry.py` | — |
| 3 | 工具状态监控 | ⚠️ PluginBox.status() 有基础状态 | `capability/plugin_box.py` | 缺: 工具调用延迟/成功率 Dashboard |
| 4 | 工具使用统计 | ✅ ToolStatsTracker + 前端面板 | `capability/tool_stats.py` + `MCPManage.vue` | 🆕 2026-07-15 已补齐 |
| 5 | 20+ 工具满分标准 | ✅ 23 tools (17 Skills + 6 Flows) | — | — |
| 6 | 热插拔 | ✅ `POST /api/mcp/reload` | `mcp/registry.py::reload()` | — |

**MCP 得分预估: 24/25**（扣 1 分：麒麟实机工具调用未验证）

---

## 二、安全校验能力 (30%)

| # | 官方要求 | v0.9.0 实际 | 证据 | 缺口 |
|---|---------|------------|------|------|
| 1 | 多层级安全防护 | ✅ 三层防御 30/35/35 | `safety_gate/three_layer_defense.py` (test: 6/6) | — |
| 2 | 静态风险评估 | ✅ 四级风险矩阵 | `safety_gate/risk.py` | — |
| 3 | 动态意图审计 | ✅ 意图识别 + 审计 | `safety_gate/intent.py` | — |
| 4 | 受限执行环境 | ✅ 4 层沙箱隔离 | `sandbox/` (setuid+rlimit+OverlayFS+mount_ns) | **麒麟实机环境未验证** |
| 5 | 用户确认流程 | ✅ S4 审批队列 + 二次确认 | `confirm/confirmation.py` | — |
| 6 | 自动回滚 | ✅ SnapshotManager + OverlayFS | `sandbox/overlay.py::rollback()` | — |
| 7 | MAC/SELinux 检查 | ✅ 执行前钩子 | `safety_gate/mac_checker.py` | **KYSEC enforce 模式未验证** |
| 8 | 命令注入防御 | ✅ | `safety_gate/injection_defense.py` | — |
| 9 | 沙箱穿透检测 | ✅ 12 探针 + 7 策略 Fuzzer | `sandbox/probes.py` + `sandbox/fuzzer.py` | — |
| 10 | 熔断降级 S0-S4 | ✅ | `resilience/` (budget+circuit+degradation) | — |

**安全得分预估: 27/30**（扣 3 分：麒麟实机 KYSEC enforce 未验证）

---

## 三、推理链路可追溯性 (25%)

| # | 官方要求 | v0.9.0 实际 | 证据 | 缺口 |
|---|---------|------------|------|------|
| 1 | 全链路追踪 | ✅ trace_id 贯穿 5 层 | `audit/spine.py` (IncidentSpine) | — |
| 2 | 五阶段记录 | ✅ receive→plan→safety→exec→post_verify | `audit/trace.py` (六阶段) | — |
| 3 | 数据持久化 | ✅ JSONL append-only + SQLite plans.db | `storage/` (5py) | — |
| 4 | 可视化分析 | ✅ TraceView.vue (时间线/DAG/热力图) | `frontend/src/views/TraceView.vue` | — |
| 5 | 卷宗导出 | ✅ `GET /api/trace/{id}/export` | — | — |
| 6 | 推理全链路测试 | ✅ 8/8 通过 | `tests/test_reasoning_trace.py` | — |
| 7 | Token 管理 | ✅ TokenManager + 上下文治理 | `utils/token_manager.py` + `agent/react_context.py` | — |

**追溯得分预估: 25/25**

---

## 四、系统架构与创新 (20%)

| # | 官方要求 | v0.9.0 实际 | 证据 | 缺口 |
|---|---------|------------|------|------|
| 1 | 模块化设计 | ✅ 34 模块, 260 py | 完整目录树 | — |
| 2 | 性能优化 | ⚠️ ReAct 上下文治理 + 缓存 | `agent/react_context.py` | **缺: 系统级性能基准报告** |
| 3 | 技术创新 | ✅ 4 层沙箱 + 装箱体系 + Fuzzer | — | — |
| 4 | 用户体验 | ✅ Vue3 13 页 + 双模式 + 画布 | `frontend/` | — |
| 5 | 麒麟 LoongArch 适配 | ⚠️ 有部署文档但无实机验证 | `docs/DEPLOY_KYLIN_LOONGARCH.md` | **缺: 麒麟实机验证报告** |
| 6 | 三方统一契约 | ✅ 前后端+文档统一 JSON | `triple_unify.json` + `verify_triple_unify.py` | — |
| 7 | 文档体系 | ✅ 9 份规范 + 体验驱动 + 技术方案 | — | — |

**创新得分预估: 17/20**（扣 3 分：无系统性能基准、无麒麟实机报告）

---

## 五、得分汇总

| 维度 | 权重 | v0.9.0 预估 | 旧文档声称 | 差异 |
|------|------|------------|-----------|------|
| MCP 插件丰富度 | 25% | **24/25** | 23.75/25 | 🆕 工具统计面板+审批UI已补齐 |
| 安全校验能力 | 30% | **27/30** | 27/30 | 扣 3 分：麒麟 KYSEC enforce 未实机验证 |
| 推理链路可追溯性 | 25% | **25/25** | 23.75/25 | 满分 |
| 系统架构与创新 | 20% | **17/20** | 18/20 | 缺麒麟实机验证 + 性能基准 |
| **总分** | **100%** | **93/100** | 92.5/100 | 🆕 +2 分（工具面板+审批UI） |

---

## 六、旧 A2_STANDARDS 文档的严重错误

| 错误 | 说明 |
|------|------|
| ❌ 引用 `optimization/` 模块 | 该模块已在 2026-06-08 删除（MASTER_PLAN §10.1） |
| ❌ 引用 `plugins/plugin_manager.py` | 已被 `skills/registry.py` 取代 |
| ❌ 声称 Streamlit 为主 UI | 现在以 Vue3 :8900 为准 |
| ❌ 路径 `/home/oy0/` | 不存在，实际在 `~/security-agent` |
| ❌ 声称 49 个工具 | 实际 17 Skills + 6 Flows = 23 个 |
| ❌ "优化统计"表 | 引用已删除的 optimization/ 模块数据 |
| ❌ "自动回滚 待完善" | v0.9.0 已实现（OverlayFS rollback） |
| ❌ "Web端追踪 待完善" | v0.9.0 已有 TraceView.vue |

---

## 七、必须补齐的 5 个缺口

### 缺口 1: 工具使用统计面板 🔴 P0

**要求**: MCP 评分维度明确要求「工具使用统计」  
**现状**: 无  
**方案**: 
- 前端新增 `/mcp/stats` 页面或 MCPManage 内嵌统计卡片
- 后端 `capability/tool_box.py` 添加调用计数 + 延迟记录
- API: `GET /api/mcp/stats` 返回 `{"tool_name": {"calls": N, "avg_latency_ms": M, "error_rate": X}}`

### 缺口 2: 麒麟 LoongArch 实机验证报告 🔴 P0

**要求**: 赛题明确目标平台是麒麟，必须有实机运行证据  
**现状**: 只有部署文档，无截图/录屏/验证记录  
**方案**:
- 新建 `docs/deploy/KYLIN_VERIFICATION.md`
- 包含: 实机环境信息（`uname -a`、KYSEC 状态）、启动截图、核心功能运行截图、三层防御/MAC 检查验收

### 缺口 3: 系统性能基准报告 🟡 P1

**要求**: 创新维度要求「性能优化」需有量化证据  
**现状**: benchmark.py 只测功能 pass/fail，不测性能  
**方案**:
- `benchmark.py --perf` 增加: API 延迟分布、内存占用、沙箱启动耗时
- 产出 `PERFORMANCE_BENCHMARK.md`

### 缺口 4: 提交规范自检 🟡 P1

**要求**: SUBMISSION_CHECKLIST.md 的每项都需要验证  
**方案**:
- 自动化 `scripts/verify_submission.py` — 逐条检查 checklist
- 包括: 文件完整性、配置文件、LICENSE、README、代码注释率

### 缺口 5: 演示脚本更新 🟡 P1

**要求**: DEMO_SCRIPT.md 需覆盖 v0.9.0 新功能  
**现状**: 旧脚本只覆盖三层防御 + Streamlit  
**方案**:
- 新增演示路径: 沙箱透明化→告警降噪→终端智能→文档活化→边界自检→知识自愈

---

## 八、立即可行动

```bash
# P0-1: 工具统计 API
# 新建 security_agent/capability/tool_stats.py
# 前端 MCPManage.vue 内嵌统计卡片

# P0-2: 麒麟实机验证
# 在麒麟 V11 LoongArch 上运行:
python scripts/benchmark.py  # 全部功能测试
# 截图留存到 docs/deploy/screenshots/

# P0-3: 提交自检
python scripts/verify_submission.py  # 待建

# P0-4: 更新 A2_STANDARDS 文档
# 本文档替代旧的 A2_STANDARDS_AND_COMPLETION.md
```

---

*生成: 2026-07-13 · 基于 v0.9.0 代码实际状态*

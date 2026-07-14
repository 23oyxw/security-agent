# 优化执行计划（已归档）

> **基线**：2026-05-30 · **已归并至** [MASTER_PLAN.md §10](architecture/MASTER_PLAN.md)（2026-06-08 重构日志）  
> 本文保留供历史参考。

---

## 图例

| 符号 | 含义 |
|------|------|
| ⬜ | 未开始 |
| 🔄 | 进行中 |
| ✅ | 已完成 |
| 👤 | 需人工（浏览器 / 麒麟实机） |

---

## P0 — 今天必须完成（演示就绪）

| # | 任务 | 负责人 | 状态 | 验收 |
|---|------|--------|------|------|
| P0-1 | 写入本计划并同步 `MASTER_PLAN` 引用 | Agent | ✅ | 本文存在 |
| P0-2 | 完善 `.gitignore`（node_modules、qt01、aiflowy、.cursor） | Agent | ✅ | 已更新 |
| P0-3 | 版本号统一到 **0.7.0**（`api/__init__.py` 等） | Agent | ✅ | `__version__` = 0.7.0 |
| P0-4 | `AgentChat` 展示 `trace_id` / `degradation_level` / `fallback_used` | Agent | ✅ | WS+REST；WS 补 `fallback_used` |
| P0-5 | 联调脚本 + 浏览器清单 | Agent | ✅ | `scripts/p0_frontend_checklist.sh`（P0 已完成） |
| P0-6 | 回归包一键跑通 | Agent | ✅ | `scripts/run_regression.sh` 全过 |
| P0-7a | **P0 API 段 curl 签字**（`p0_frontend_checklist.sh`） | Agent | ✅ | 10/10 @ :8900 |
| P0-7 | **浏览器 10 页人工签字** | 👤 用户 | 👤 | 清单每项打勾 |
| P0-8 | 首次 `git commit`（主干代码，不含 qt01 可选） | 👤/Agent | 👤 | 用户确认后提交 |

### P0 验收命令

```bash
cd /home/oy0/security-agent
bash scripts/run_regression.sh
PYTHONPATH=. .venv/bin/python scripts/e2e_api_smoke.py
bash scripts/p0_frontend_checklist.sh   # API 段（需 API 已启动）
# 浏览器：P0 已通过验收，无需再执行
```

### P0 启动（答辩拓扑）

```bash
bash boot_start.sh          # :8900 + dist
# 或
bash boot_start.sh --dev    # :5173 → proxy :8900
```

---

## P1 — 联调后本周（工程质量 + 文档真值）

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| P1-1 | 更新 `MASTER_PLAN` §8 / §3（E2E 已 28/28、mac_checker 已接线、boot_start 已含 Vue） | ✅ | 2026-05-30 已修 §8 风险表 |
| P1-2 | 更新 GAP_ANALYSIS（沙箱/MCP/热插拔等过时条目） | ✅ | 已由 `A2_OFFICIAL_GAP_ANALYSIS.md` 替代 |
| P1-3 | `aiflowy-main/` 去留决策 | ✅ | [REFERENCE_LIBS.md](REFERENCE_LIBS.md)：保留本地、gitignore、不集成 |
| P1-4 | 麒麟实机：executor + mac_checker 一条路径实测 | 👤 | 赛题 KYSEC |
| P1-5 | 演示脚本统一端口说明（8900 vs 8000） | ✅ | README + `boot_start.sh` 头注释 |
| P1-6 | GitHub Actions：§7 单测 + e2e smoke | ✅ | `.github/workflows/regression.yml` |

---

## P2 — 有空再做（不挡答辩）

| # | 任务 |
|---|------|
| P2-1 | qt01 仅参考：`.gitignore` 忽略或 git submodule |
| P2-2 | Vue Flow 只读流程图 |
| P2-3 | 多 Agent / Dify 深集成 |
| P2-4 | Pinia agent/safety store 拆分 |

---

## 执行日志

| 日期 | 完成项 | 备注 |
|------|--------|------|
| 2026-05-30 | P0-1～P0-6、P1-1 | 计划、gitignore、版本、AgentChat、脚本、回归、MASTER 同步 |
| 2026-05-30 | P0-7 | 👤 待用户浏览器签字 |
| 2026-05-30 | P0-8 | 👤 待用户确认后首次 commit |
| 2026-05-30 | P1-2～P1-6 | GAP 更新、REFERENCE_LIBS、端口说明、CI workflow |
| 2026-05-30 | P0-7a | `p0_frontend_checklist.sh` 10/10；修正 evaluate 请求体 `target` |
| 2026-05-30 | 联调增强 | LLM/LiteLLM 配置、Token+费用+上下文、L1/L2/L3/Trace 前端标识、Skill flow×4、登录页演示账号 |

### 2026-05-30 增量（相对原计划）

| 项 | 状态 | 说明 |
|----|------|------|
| LiteLLM 模型名 / deepseek 前缀 | ✅ | `litellm_config.yaml` + `config.py` |
| Agent Token 费用 + 上下文占比 | ✅ | `cost.py` · AgentChat 侧栏 |
| L2 scan_report 5 步 + HTML | ✅ | `skills/flows/runner.py` |
| L2 block_process (kill) | ✅ | 第 4 条 flow |
| 前端 L1/L2/L3/Trace 分层 UI | ✅ | `ArchitectureLayers.vue` · 菜单改名 |
| 登录页演示账号提示 | ✅ | `Login.vue` |
| P0-7 浏览器签字 | 👤 | 待用户按更新后清单打勾 |
| P0-8 git commit | 👤 | 用户未要求则不提交 |
| Trace/告警时间对齐 | ✅ | 阶段增量耗时、北京时间戳、告警 occurred/published 分列 |
| 文档归并 | ✅ | 删 8 份重复 optimization 报告 → [KNOWN_ISSUES.md](KNOWN_ISSUES.md) |
| 告警自动刷新 + L2 处置入口 | ✅ | `Alerts.vue` · 顶栏跳转 `/flows` |
| Trace 列表去重 + 对话 L2 统一 trace_id | ✅ | `trace_routes.py` · `brain.py` |
| 告警 RCA 展示 | ✅ | `skill_flow_format.py` · `incident_responder` on_alert |

---

*关联：[MASTER_PLAN.md](architecture/MASTER_PLAN.md) · [KNOWN_ISSUES.md](KNOWN_ISSUES.md) · [LLM_MODEL_FIX.md](LLM_MODEL_FIX.md)*

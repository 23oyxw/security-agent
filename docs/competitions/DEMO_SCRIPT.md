# 答辩演示脚本（约 5 分钟）

> 一键启动：`bash boot_start.sh` → 浏览器 `http://<主机>:8900`  
> 文档入口：[docs/INDEX.md](../INDEX.md) · 提交清单：[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md)  
> 命令行演示：`bash scripts/demo_three_layer_defense.sh`

## 演示路径 A — 浏览器（推荐）

### 阶段一：B/S 架构 + 多维感知（60s）

| # | 页面 | 操作 | 得分点 |
|---|------|------|--------|
| 1 | 登录 `/login` | admin / admin123，展示版本号水印 | B/S 国产化 |
| 2 | 仪表盘 `/` | 查看 CPU/内存/磁盘/进程数，L1-L5 流水线步骤 | ① 多维感知 |
| 3 | 态势总览 `/perception` | 8 维只读仪表盘：网络/端口/CPU/内存/磁盘/链路/权限/状态 | L1 静态感知 |

### 阶段二：三层防御 + 审批闭环（90s）🆕

| # | 页面 | 操作 | 得分点 |
|---|------|------|--------|
| 4 | 安全防护沙箱 `/safety` | 输入 `rm -rf /tmp/test` 意图「清理临时文件」→ 点击「评估风险」 | ③ 安全意图校验 |
| 5 | 同上 | 展示三层防御评分卡（静态30% + 意图35% + 受限执行35%）+ 决策路径 | 三层防御 30/35/35 |
| 6 | 同上 | 输入高危命令 `dd if=/dev/zero of=/dev/sda` → 评估 → 显示「⚠️ 需要管理员审批」 | ESCALATE 机制 |
| 7 | 同上 | 点击「提交审批申请」→ 获取审批单号 → 展示轮询状态 | 🆕 S4 人工审批 |
| 8 | 同上（管理员视角） | 底部「🔐 审批队列」→ 查看待审批项 → 点击「批准」 | 🆕 审批管理面板 |
| 9 | 同上（切回用户） | 轮询检测到通过 → ✅「审批已通过」→ 点击执行 | 🆕 审批闭环 |
| 10 | 命令执行器 `/executor` | 执行 `ls -la /tmp`（沙箱模式）→ 展示退出码/耗时/快照 ID | ④ 最小权限 + 沙箱 |

### 阶段三：MCP + Trace + 画布（90s）

| # | 页面 | 操作 | 得分点 |
|---|------|------|--------|
| 11 | MCP 管理 `/mcp` | 展示 17 Skills + 工具调用统计表格（调用次数/成功率/延迟） | ② MCP 插件化 |
| 12 | 同上 | 点击「热插拔重载」→ 工具列表刷新 | 🆕 工具统计面板 |
| 13 | Trace 卷宗 `/trace` | 查看 trace 列表 → 展开时间线/DAG 视图 | ⑤ 推理链路溯源 |
| 14 | 五层画布 `/canvas` | 主线泳道高亮 L1→L2→GATE→L3→L4→L5 | 架构 · 三 Agent |
| 15 | 流水线观测 `/workflow` | Mainline 统筹 Tab + Agent 协同 | T0–T3 封装 |
| 16 | 知识库 `/knowledge` | 搜索「SSH 暴力破解」→ 展示 Playbook 结果 | Gitee Wiki 索引 |

### 阶段四：加分项（60s）

| # | 页面 | 操作 | 得分点 |
|---|------|------|--------|
| 17 | 边界对抗 `/l1/boundary` | 展示 6 权限跃迁探针 + 7 变异策略 | 🆕 边界韧性 |
| 18 | L5 量化 `/l5` | 六维指标仪表盘 + 散点/热力图 | 🆕 L5 量化分析 |
| 19 | 用户管理 `/users` | 三角色（admin/operator/viewer）+ 创建用户 | RBAC 权限隔离 |

## 演示路径 B — 命令行

```bash
bash boot_start.sh
bash scripts/demo_three_layer_defense.sh http://127.0.0.1:8900
PYTHONPATH=. python scripts/e2e_api_smoke.py
python scripts/benchmark.py
```

## v0.9.0 新功能演示要点

| 功能 | 演示方式 | 文件 |
|------|---------|------|
| 7 层沙箱隔离 | `/safety` 执行写操作 → 自动 COW | `sandbox/` |
| 5 层告警静噪 | `/alerts` 查看过滤/去重/节流/关联 | `notify/` |
| 智能终端 | `/executor` 输入自然语言意图 → 命令建议 | `terminal/` |
| 文档激活 | `/knowledge` TF-IDF 双索引检索 | `document/` |
| 边界 Fuzzer | `/l1/boundary` 12 探针 + 7 变异策略 | `sandbox/fuzzer.py` |
| 知识自愈 | 后端自动 stale 检测 + 一致性检查 | `knowledge/guard.py` |
| 能力装箱 | `/mcp` ToolBox + FlowBox + PluginBox 统一入口 | `capability/` |
| 人工审批 | `/safety` 提交→队列→批准→执行 闭环 | 🆕 本次新增 |

## 自动化验收

```bash
PYTHONPATH=. python scripts/e2e_api_smoke.py
# 期望 全部 PASS

python scripts/benchmark.py
# 期望 6 套件全通过，健康度 100/100
```

## 话术要点

- **三层防御**：L1 静态规则 30% + L2 意图审计 35% + L3 麒麟环境 35%，综合 verdict 驱动 allow/confirm/approve/escalate/deny。
- **最小权限**：写操作进 OverlayFS 沙箱；PrivilegeBroker 自动降权到 `agent_ops` 用户。
- **审批闭环**：高危操作自动升级到人工审批 → SQLite 持久化队列 → 管理员批准/拒绝 → 轮询通知。
- **MCP**：17 Skills 分四簇（metrics/logs/repair/dispatch），热插拔 `POST /api/mcp/reload`。
- **溯源**：每次评估/执行带 `trace_id`，`data/traces/*.jsonl` append-only 不可篡改。
- **麒麟适配**：禁用 LiteLLM Docker（龙架构无镜像），直连 API；mac_checker 对接 KYSEC。

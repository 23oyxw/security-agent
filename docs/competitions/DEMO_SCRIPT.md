# 答辩演示脚本（约 3 分钟）

> 一键启动：`bash boot_start.sh` → 浏览器 `http://<主机>:8900`  
> 文档入口：[docs/INDEX.md](../INDEX.md) · 提交清单：[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md)  
> 命令行演示：`bash scripts/demo_three_layer_defense.sh`

## 演示路径 A — 浏览器（推荐）

| 顺序 | 页面 | 操作 | 得分点 |
|------|------|------|--------|
| 1 | 登录 | admin / admin123 | B/S 国产化 |
| 2 | 仪表盘 | 查看 CPU/内存/MCP | ① 多维感知 |
| 3 | 安全门禁 | 输入 `rm -rf /` + 意图「清理」→ 三层防御评分 | ③ 安全意图校验 |
| 4 | 安全执行器 | 执行 `ls -la /tmp`（勾选确认） | ④ 最小权限 + 沙箱 |
| 6 | 推理溯源 | 查看 trace 列表 | ⑤ 推理链路溯源 |
| 7 | 五层画布 | `/canvas` 主线高亮 | 架构 · 三 Agent |
| 8 | 流水线观测 | `/workflow` 主线统筹 Tab | T0–T3 封装 |
| 9 | 任务分析 | `/reports` 上传 Prompt | L1 分层分析 |
| 10 | MCP 管理 | 热插拔重载 | ② MCP 插件化 |
| 11 | Skill 流程 | 运行 `scan_report` | L2 封装 |

## 演示路径 B — 命令行

```bash
bash boot_start.sh
bash scripts/demo_three_layer_defense.sh http://127.0.0.1:8900
PYTHONPATH=. .venv/bin/python scripts/e2e_api_smoke.py
```

## 自动化验收

```bash
PYTHONPATH=. .venv/bin/python scripts/e2e_api_smoke.py
# 期望 全部 PASS
```

## 话术要点

- **三层防御**：L1 静态规则 30% + L2 意图审计 35% + L3 麒麟环境 35%，综合 verdict 驱动 allow/confirm/deny。
- **最小权限**：写操作进沙箱；`mac_checker` 在 executor 前拦截 SELinux/KYSEC 越权。
- **MCP**：Skill 热插拔 `POST /api/mcp/reload`，不重装进程即可刷新工具列表。
- **溯源**：每次评估/执行带 `trace_id`，`data/traces/*.jsonl` 可复盘。

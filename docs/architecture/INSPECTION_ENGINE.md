# 巡检引擎（华测自动化测试迁移）

> 测试语义：用例编排 → 命令执行 → 断言 → 报告；运维语义：只读基线巡检。

## 模块

| 路径 | 说明 |
|------|------|
| `data/inspection/suites/*.yaml` | 巡检用例集 |
| `data/baselines/kylin_v11.json` | 麒麟基线元数据 |
| `security_agent/inspection/runner.py` | 执行 + 报告 |
| `configs/notify_channels.yaml` | 可插拔 Webhook（默认关，不绑飞书） |
| `POST /api/inspection/run` | 触发巡检 |
| `GET /api/inspection/risk/predict` | L5 时序风险窗口 |

## 闭环

修复 `POST /api/repair/trigger` 成功后自动复测 `kylin_baseline`。

## 定时

```bash
python scripts/scheduled_patrol.py inspection
```

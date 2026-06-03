# 参考库与外部目录说明

> **决策日期**：2026-05-30 · 见 [OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md) P1-3

## 原则

- **A 线主干**：仅 `security_agent/`、`frontend/`、`tests/`、`scripts/`、`docs/` 等。
- **不 import、不部署** 下列参考目录；本地可保留，**默认 `.gitignore` 不提交**。

## 目录

| 路径 | 体积 | 用途 | 决策 |
|------|------|------|------|
| `qt01/` | ~619M | C 线参考：三层防御源码、Qt 流程图、完整 pytest | **保留本地**，答辩对照；不并入主干 |
| `aiflowy-main/` | ~83M | 第三方 AI 工作流参考 | **不集成**；若不需要可整目录移出仓库外归档 |

## 若需释放磁盘

```bash
# 仅当确认不再需要时（先备份）
# mv qt01 /archive/security-agent-qt01-ref
# mv aiflowy-main /archive/aiflowy-main
```

## 与赛题交付的关系

答辩与验收以 **FastAPI :8900 + Vue dist** 为准（`bash boot_start.sh`），不以 qt01 Streamlit/Qt 为主路径。

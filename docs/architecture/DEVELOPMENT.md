# 开发流程（DEVELOPMENT）

给队友、指导老师、答辩时「我们如何做出来的」用。

## 1. 环境准备

```bash
cd /path/to/security-agent
# 安装 uv: https://github.com/astral-sh/uv
uv sync
cp .env.example .env   # 编辑 LLM_API_KEY 等
```

### 多模型配置（`.env`）

```ini
# 对话 Agent — MiMo（默认旗舰）
LLM_API_KEY=your_mimo_key
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_MODEL=mimo-v2.5-pro

# 自主任务 — DeepSeek R1
AUTONOMOUS_API_KEY=your_deepseek_key
AUTONOMOUS_BASE_URL=https://api.deepseek.com/v1
AUTONOMOUS_MODEL=deepseek-reasoner

# 批量任务 — DeepSeek V3.2
BUDGET_API_KEY=your_deepseek_key
BUDGET_BASE_URL=https://api.deepseek.com/v1
BUDGET_MODEL=deepseek-chat

# RAG 嵌入（需 OpenAI Key）
EMBEDDING_API_KEY=your_openai_key
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
```

### 侧栏模型切换

UI 侧栏 `🧠 对话模型` 下拉框可一键切换：
- **MiMo v2.5 Pro（Agent 旗舰）** — 默认，重度 agent 任务
- **MiMo v2.5（快速轻量）** — 日常快速问答
- **DeepSeek V3.2（批量/高频）** — 批量生成
- **DeepSeek R1（深度推理）** — 自主规划

切换时自动重建 Agent 并清空对话历史。

### LiteLLM Proxy（可选）

```bash
cp litellm_config.example.yaml litellm_config.yaml  # 编辑 API Key
pip install 'litellm[proxy]'
litellm --config litellm_config.yaml --port 4000
# 然后 .env 里 BASE_URL 全部改为 http://localhost:4000/v1
```

## 2. 日常开发循环

```text
改代码 → 本地启动 → 手点/冒烟 → 校准（若动规则）→ 提交
```

| 步骤 | 命令 / 操作 |
|------|-------------|
| 启动 UI | `bash boot_start.sh` |
| 停止 UI | `bash boot_stop.sh` |
| 冒烟测试 | `uv run python scripts/smoke_test.py` |
| 规则/检测校准 | `uv run python scripts/demo_risk.py calibration` |
| 终端边界 | `uv run python scripts/demo_risk.py boundary` |
| 看日志 | `tail -f data/logs/streamlit.log` |

## 3. 改不同模块时看什么

| 改什么 | 主要文件 | 必跑测试 |
|--------|----------|----------|
| 高危进程规则 | `config.py`、`scanner/engine.py` | `demo_risk.py calibration` |
| 终端白名单 | `rules/engine.py` | `demo_risk.py boundary` |
| 新工具 | `tools/registry.py` | `smoke_test.py` |
| 新 Skill | `skills/xxx/skill.py`、`skills/base.py` | `smoke_test.py` + 自动注册验证 |
| 告警升级策略 | `agent/escalation.py` | 手开监控 + 触发告警 |
| 监控项 | `monitor/*.py` | 手开监控 + 看事件 |
| 页面布局 | `ui/pages*.py`、`ui/layout.py` | 浏览器点一遍 |
| 知识库/建议 | `knowledge/playbooks.py`、`agent/advisor.py` | 智能助手提问 |
| 模型配置 | `.env`、`config.py` MODEL_PRESETS | 切换模型后对话测试 |
| 报告预览 | `ui/report_preview.py` | 报告中心 |

## 4. 分支与提交建议（团队）

- `main`：可演示、冒烟通过  
- 功能分支：`feat/xxx`、`fix/xxx`  
- 提交前至少：`smoke_test` +（动检测时）`calibration` 全绿  
- **不要提交** `.env`、`data/audit.log`（含环境信息）

## 5. 版本号约定

- 文档：**v0.9.0**（功能冻结用于比赛时可打 tag）
- `pyproject.toml` 的 version 与 README 标题建议保持一致

## 6. 发布 / 演示前检查清单

- [ ] `.env` 已配置有效 `LLM_API_KEY`  
- [ ] `boot_start.sh` 能打开 http://127.0.0.1:8501  
- [ ] 风险演练 → 校准 66/66、边界 35/35  
- [ ] 报告中心表格 + 网页预览正常  
- [ ] 自主运维：终端 `ps aux`、任务结果页可滚动  
- [ ] 演示脚本录屏 3～5 分钟（见 [PLAIN_GUIDE.md](PLAIN_GUIDE.md) 场景 A/B/C）

## 7. 可选：MCP 调试

```bash
uv run python cli.py --mcp
# 另开终端用 MCP Client 连接；失败不影响 Streamlit 主流程
```

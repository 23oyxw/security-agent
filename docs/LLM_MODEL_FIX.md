# LLM 模型名配置说明（修复 400 Invalid model）

## 现象

- 主模型：`Invalid model name ... mimo-v2.5`
- 备用：`deepseek-v4-flash` 经 LiteLLM 时报错 — 代理只认 **别名** `mimo-chat` / `deepseek-chat`

## 两种部署

### A. 经 LiteLLM（你当前环境）

`.env` 建议：

```bash
USE_LITELLM_PROXY=true
LLM_BASE_URL=http://127.0.0.1:4000/v1
LLM_API_KEY=sk-1234
LLM_MODEL=mimo-chat
LITELLM_FALLBACK_MODEL=deepseek-chat
BUDGET_BASE_URL=http://127.0.0.1:4000/v1
BUDGET_MODEL=deepseek-chat
```

确认代理已启：`bash scripts/litellm_manager.sh start` 或 Docker。

## LiteLLM 配置常见坑

`configs/litellm_config.yaml` 里 `litellm_params.model` 在已设置 `api_base: https://api.deepseek.com/v1` 时，必须用 **`deepseek-v4-flash` / `deepseek-v4-pro`**，不能写 `deepseek/deepseek-v4-flash`（会 400）。

修改配置后重启代理：

```bash
bash scripts/litellm_docker.sh restart
# 或
bash scripts/litellm_manager.sh restart
bash scripts/restart_api.sh
```

### B. 直连 MiMo（不经 LiteLLM）

```bash
USE_LITELLM_PROXY=false
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_MODEL=<你的 Key 在 /v1/models 里支持的 id>
```

## 应用后

```bash
bash scripts/restart_api.sh
```

答辩无 Key 时：Agent 用 **「生成扫描报告」**，不依赖 LLM。

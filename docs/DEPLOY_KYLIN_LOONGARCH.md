# 麒麟高级服务器 V11 (Swan25) · LoongArch 部署指南

> 实验机：**dnf** 包管理 · **龙架构** · 与 x86 开发机分开构建，勿拷贝 `.venv`。

## 1. 架构差异（必读）

| 项目 | x86 开发机 | LoongArch 实验机 |
|------|------------|------------------|
| `.venv` | 可用 | ❌ **禁止拷贝**，必须本机 `uv sync` |
| `frontend/dist` | 可选本机构建 | ✅ 静态资源可随 tar 包带走 |
| LiteLLM Docker | 常见 | ⚠️ 镜像多为 amd64/arm64，**龙架构常无镜像** |
| 推荐 LLM 模式 | 可选代理 | **直连 API**（`USE_LITELLM_PROXY=false`） |

打包文件：`dist/security-agent-v*.tar.gz`（不含 `pgdata2`、不含 `.venv`）。

## 2. 系统依赖（dnf）

```bash
sudo dnf install -y \
  python3 python3-pip python3-devel \
  gcc gcc-c++ make \
  git curl \
  nodejs npm \
  psutil  # 若 dnf 有 python3-psutil 可改为 python3-psutil
```

可选（仅当你确认有 **loongarch** 镜像且 KYSEC 允许 Docker）：

```bash
sudo dnf install -y docker docker-compose-plugin
sudo systemctl enable --now docker
```

浏览器：使用系统自带 **Chromium / Firefox** 访问控制台，无需额外安装。

## 3. 解压与初始化

```bash
tar -xzf security-agent-v0.7.0-*.tar.gz
cd security-agent-v0.7.0-*

# 一键脚本（推荐）
bash scripts/bootstrap-kylin-loongarch.sh

# 或手动：
cp .env.example .env
# 编辑 .env（见下文「实验机 .env 模板」）
bash start.sh
# 或麒麟桌面双击: 打开应用.sh
# 停止: bash stop.sh
```

## 4. 实验机 `.env` 模板（推荐）

```env
# 龙架构实验机：直连模型，不依赖 LiteLLM 容器
USE_LITELLM_PROXY=false
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_MODEL=mimo-v2.5

SEC_API_PORT=8900
SEC_API_HOST=0.0.0.0
```

若现场必须用 LiteLLM，需确认 `docker pull` 在龙架构可用；否则保持 `false`，应用内 **Fallback** 仍可用。

## 5. 前端

- 包内已有 `frontend/dist` → 直接 `boot_start.sh` 即可。
- 若无 `dist`：需本机 `nodejs` + `cd frontend && npm install && npm run build`（龙架构 npm 源较慢，建议在 x86 机先 build 再打包）。

## 6. KYSEC 常见问题

| 现象 | 处理 |
|------|------|
| `KYSEC: 权限不够` 执行脚本 | `chmod +x boot_start.sh scripts/*.sh`；或 `bash boot_start.sh` 显式调用 |
| `uvloop` / libuv 编译失败 | 已改用 `uvicorn`（非 standard），重新 `uv sync` |
| Docker 无权限 | `.env` 设 `USE_LITELLM_PROXY=false` |
| `mac_checker` / kysec | 代码已挂钩；在实验机跑一次安全执行器验收 |

## 7. 验收

```bash
bash scripts/run_regression.sh
PYTHONPATH=. .venv/bin/python scripts/e2e_api_smoke.py
curl -s http://127.0.0.1:8900/api/health
```

浏览器：`http://<实验机IP>:8900/`（防火墙放行 **8900**）。

## 8. 赛题得分相关

- **国产化**：`config.platform_label()` 会识别麒麟。
- **KYSEC**：`security_agent/safety_gate/mac_checker.py` + `terminal/executor.py` 执行前检查。
- **B/S**：Vue 静态页 + FastAPI，适配麒麟浏览器。

## 相关文档

- [DEPLOY_OFFLINE.md](DEPLOY_OFFLINE.md) · [发给小组-使用说明.txt](../发给小组-使用说明.txt) · [LITELLM_GUIDE.md](LITELLM_GUIDE.md)

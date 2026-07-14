# 换机 / 离线部署说明

## 原则

| 内容 | 是否打进 tar 包 | 目标机怎么办 |
|------|----------------|--------------|
| 源码 `security_agent/`、`frontend/`、`scripts/` | ✅ 要 | 直接使用 |
| `.venv` | 精简包 ❌ | `uv sync`（`boot_start.sh` 会做） |
| `.env`（含 Key） | 精简包 ❌ | `cp .env.example .env` 后编辑 |
| `data/litellm/pgdata2` | ❌ **永远不要** | Docker 首次 `compose up` 自动建库 |
| `data/logs`、`data/alerts`、`.db` | 精简包 ❌ | 运行后生成 |
| `qt01/`、`aiflowy-main/` | ❌ | 仅本地参考，见 `.gitignore` |
| `frontend/dist` | 可选 | 无则 `boot_start.sh` 会 `npm run build` |

`pgdata2` 权限不够的原因：容器内 Postgres 属主为 `nobody`、目录 700，**不是给你拷贝的**，换机后让 Docker 重建即可。

## 推荐：官方打包脚本

```bash
cd /home/oy0/security-agent
bash scripts/package-release.sh
# 产物: dist/security-agent-v0.9.0-YYYYMMDD.tar.gz
```

内网同一套配置（含已调好的 `.env`、`.venv`）：

```bash
bash scripts/package-release.sh --full
```

## 目标机启动

```bash
tar -xzf security-agent-v*.tar.gz
cd security-agent-v*
cp .env.example .env    # 填 LLM_API_KEY 等
bash boot_start.sh
# 访问 http://<IP>:8900/
```

需 LiteLLM 时，在 `.env` 中：

```env
USE_LITELLM_PROXY=true
LLM_BASE_URL=http://127.0.0.1:4000/v1
LLM_MODEL=mimo-chat
```

并安装 Docker；`boot_start.sh` 会拉起 `configs/docker-compose.litellm.yml`。

## 不要用「整目录复制」

直接 `cp -a security-agent /新机/` 会把 `pgdata2` 一起拷过去，且权限仍不对。请用上面的 **tar 排除规则** 或 `package-release.sh`。

## 相关文档

- [发给小组-使用说明.txt](../发给小组-使用说明.txt)
- [ENTERPRISE_DEPLOY.md](ENTERPRISE_DEPLOY.md)
- [OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md)

# 提交规范清单（避免 disqualify）

> 最后更新: 2026-07-15 · v0.9.0

## 必须包含

- [x] 完整 `security-agent/` 源码目录（260 py, 34 模块）
- [x] `frontend/dist/` 非空（生产构建）
- [x] `data/mcp/workflow_manifest.json`（工作流清单）
- [x] `docs/INDEX.md`（文档总索引）
- [x] `.env.example`（不含真实 Key）
- [x] 端口 8900 启动说明（`boot_start.sh` + `START_WIN.bat`）
- [x] `VERSION` 文件（`0.9.0`）
- [x] `pyproject.toml` + `frontend/package.json` 版本对齐

## 禁止提交

- [x] `.venv` `node_modules`
- [x] 真实 API Key（`.env` 不含有效 Key）
- [x] 根目录 `.docx` / 私人 `.txt`
- [x] 未脱敏 `data/traces/`（运行时生成，已 gitignore）
- [x] `data/litellm/pgdata2`（Docker 数据库，已 gitignore）
- [x] `qt01/` `aiflowy-main/`（参考库，已 gitignore）

## 功能自检

```bash
# 1. 启动
bash boot_start.sh
# → http://127.0.0.1:8900

# 2. 版本校验
python scripts/check_version.py

# 3. 三方统一契约
python scripts/verify_triple_unify.py

# 4. 全量基准测试
python scripts/benchmark.py

# 5. E2E API 冒烟（需服务运行）
PYTHONPATH=. python scripts/e2e_api_smoke.py

# 6. 三层防御演示
bash scripts/demo_three_layer_defense.sh http://127.0.0.1:8900
```

## 页面完整性检查（浏览器 13 页）

| 页面 | 路由 | 状态 |
|------|------|------|
| 登录 | `/login` | ✅ |
| 运维概览 | `/` | ✅ |
| 智能体对话 | `/agent` | ✅ |
| 态势总览 (L1) | `/perception` | ✅ |
| 边界对抗 (L1) | `/l1/boundary` | ✅ |
| 知识库检索 | `/knowledge` | ✅ |
| 安全防护沙箱 (L2) | `/safety` | ✅ |
| 告警中心 | `/alerts` | ✅ |
| 工具能力中心 (L3) | `/mcp` | ✅ |
| Trace 卷宗 (L4) | `/trace` | ✅ |
| L5 链路量化 | `/l5` | ✅ |
| 五层架构画布 | `/canvas` | ✅ |
| 流水线观测 | `/workflow` | ✅ |
| 用户管理 | `/users` | ✅ (admin only) |

## 权威文档入口

- 架构：[architecture/FINAL_ARCHITECTURE.md](../architecture/FINAL_ARCHITECTURE.md)
- 结构：[REPO_STRUCTURE.md](../REPO_STRUCTURE.md)
- 版本：[RELEASE.md](../RELEASE.md)
- 部署：[DEPLOY_KYLIN_LOONGARCH.md](../DEPLOY_KYLIN_LOONGARCH.md)
- Windows：[deploy/WINDOWS.md](../deploy/WINDOWS.md)

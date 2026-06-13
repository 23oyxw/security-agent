# 提交规范清单（避免 disqualify）

## 必须包含

- [ ] 完整 security-agent/ 目录
- [ ] frontend/dist/ 非空
- [ ] workflow_manifest.json
- [ ] docs/INDEX.md
- [ ] .env.example（勿提交 .env）
- [ ] 端口 8900 启动说明

## 禁止提交

- [ ] .venv node_modules
- [ ] 真实 API Key
- [ ] 根目录 docx/私人 txt
- [ ] 未脱敏 data/traces

## 自检

bash boot_start.sh
PYTHONPATH=. python scripts/e2e_api_smoke.py

## 权威文档

架构 FINAL_ARCHITECTURE.md；Windows deploy/WINDOWS.md；结构 REPO_STRUCTURE.md

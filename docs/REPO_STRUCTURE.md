# 仓库结构规范（答辩版）

> 历史报告 [development/FILE_STRUCTURE_OPTIMIZATION.md](development/FILE_STRUCTURE_OPTIMIZATION.md) 已归档，以本文为准。

## 顶层

- README.md, pyproject.toml, .env.example
- boot_start.sh, START_WIN.bat
- security_agent/ 后端
- frontend/ 含 dist/ 必提交
- docs/ 全部文档
- scripts/ 验收与部署脚本
- data/contracts/triple_unify.json **三方统一真源**
- data/mcp/workflow_manifest.json 提交；data/traces 等运行时忽略

## 三方统一

| 文件 | 说明 |
|------|------|
| data/contracts/triple_unify.json | Agent / 主线 / stage / 画布映射唯一真源 |
| security_agent/contracts/loader.py | 后端加载 |
| frontend/src/constants/from-contract.js | 前端加载 |
| docs/architecture/TRIPLE_UNIFY.md | 契约说明 |
| scripts/verify_triple_unify.py | 漂移校验 |

## 后端分层

| 目录 | 职责 |
|------|------|
| agent/ | 三 Agent, brain |
| contracts/ | 三方统一契约加载 |
| pipeline/ | coordination, htn, sandbox, stage_meta |
| api/ | FastAPI |
| safety_gate/ | L2 |
| audit/, storage/ | L4 trace |
| l5/ | L5 量化 |
| skills/, tools/ | MCP |
| retrieval/ | 知识库 RAG |
| analysis/ | 任务分析 |

## 前端

views/ 页面；constants/from-contract.js 与 constants/canvas-spine-map.js 从契约派生，与 coordination.py 阶段名对齐。

## 禁止根目录新增

.docx、私人笔记、未归类脚本 → 入 docs/ 或 scripts/

详见 SUBMISSION_CHECKLIST.md

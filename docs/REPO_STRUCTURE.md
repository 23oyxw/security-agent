# 仓库结构规范（答辩版）

> 历史报告 [development/FILE_STRUCTURE_OPTIMIZATION.md](development/FILE_STRUCTURE_OPTIMIZATION.md) 已归档，以本文为准。

## 顶层

- README.md, pyproject.toml, .env.example
- boot_start.sh, START_WIN.bat
- security_agent/ 后端
- frontend/ 含 dist/ 必提交
- docs/ 全部文档
- scripts/ 验收与部署脚本
- data/mcp/workflow_manifest.json 提交；data/traces 等运行时忽略

## 后端分层

| 目录 | 职责 |
|------|------|
| agent/ | 三 Agent, brain |
| pipeline/ | coordination, htn, sandbox, stage_meta |
| api/ | FastAPI |
| safety_gate/ | L2 |
| audit/, storage/ | L4 trace |
| l5/ | L5 量化 |
| skills/, tools/ | MCP |
| retrieval/ | 知识库 RAG |
| analysis/ | 任务分析 |

## 前端

views/ 页面；constants/canvas-spine-map.js 与 coordination.py 阶段名对齐。

## 禁止根目录新增

.docx、私人笔记、未归类脚本 → 放 docs/ 或 scripts/

详见 SUBMISSION_CHECKLIST.md

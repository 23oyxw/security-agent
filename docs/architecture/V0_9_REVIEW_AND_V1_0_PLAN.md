# v0.9.0 架构总结与 v1.0 开发计划

> **版本**：v0.9.0 → v1.0.0-plan · **日期**：2026-07-13  
> **定位**：9 份文档深度审查 + 创新方向提案 + 下一阶段路线图

---

## 一、9 份文档深度审查

### ① 产品架构 — FINAL_ARCHITECTURE.md ✅ 健康

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐⭐⭐⭐ 3 Agent + 5 层流水线 + 设计原则 + 实现矩阵 |
| 时效性 | ✅ 已更新到 v0.9.0 |
| 薄弱点 | Wiki push 仍标"待建"、L5 数学模型实际薄弱 |

### ② 技术架构 — TECHNICAL_ARCHITECTURE.md ⚠️ 需更新

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐⭐⭐ 三交付线 + 模块矩阵完整 |
| 时效性 | ⚠️ 模块计数未更新到 260py、技术栈列表缺新依赖 |
| 薄弱点 | 交付线 C (qt01) 的状态表可能过时 |

### ③ UI 规范 — frontend/ARCHITECTURE.md ❌ 严重不足

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐ 仅 67 行，13 页面的组件树/状态管理/API 约定未展开 |
| 时效性 | ❌ 未提及 InfiniteCanvas、SafetyGate 合并版、L5 页面 |
| **建议** | **重写**：补全 13 页面的组件树、Pinia stores、composables |

### ④ 验收标准 — A2_STANDARDS_AND_COMPLETION.md ❌ 过时

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐⭐ 五大支柱评分标准在，但案例和得分过时 |
| 时效性 | ❌ 2026-05-22 生成，未反映 v0.9.0 的沙箱/告警/终端升级 |
| **建议** | **重写**：按 v0.9.0 重新评估五大支柱得分 |

### ⑤ 多环境部署 — deploy/ + DEPLOY_KYLIN ⚠️ 可操作但分散

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐⭐⭐ Windows/Linux/麒麟/离线 四环境有文档 |
| 薄弱点 | 麒麟环境无实机验证记录、一键部署脚本缺故障排查 |
| **建议** | 补充麒麟实机验证 checklist + 常见问题 FAQ |

### ⑥ 一键部署 — boot_start.sh + START_WIN.bat ✅ 可用

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐⭐⭐ 自动检测 Python/Node/dist/venv |
| 薄弱点 | 无麒麟 LoongArch 专用一键脚本（需手动步骤） |
| **建议** | 新建 `deploy/loongarch_boot.sh`，封装 dnf 依赖安装 + uv sync |

### ⑦ 项目目录 — REPO_STRUCTURE.md ❌ 过时

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐ 仅 56 行 |
| 时效性 | ❌ 未反映 v0.9.0 新增的 capability/document/filesystem/sandbox 等模块 |
| **建议** | 重写为完整的 260py 目录树 |

### ⑧ 三方契约 — TRIPLE_UNIFY.md + triple_unify.json ✅ 健康

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐⭐⭐⭐⭐ 前后端+文档三方统一，校验脚本可用 |
| 时效性 | ✅ 已更新 project_version 到 0.9.0 |
| 改进空间 | 契约目前手动同步，可做 pre-commit hook 自动校验 |

### ⑨ README 入口 — README.md ✅ 健康

| 维度 | 评价 |
|------|------|
| 完整性 | ⭐⭐⭐⭐ 快速开始/核心功能/验证链/需求边界 |
| 时效性 | ✅ 已更新到 0.9.0 |
| 改进空间 | 缺「架构全景图」一张图看懂 |

---

## 二、文档修复优先级

```
P0 (本周):
  □ frontend/ARCHITECTURE.md — 重写为完整的 13 页组件规范
  □ REPO_STRUCTURE.md — 重写为 260py 完整目录树
  □ A2_STANDARDS_AND_COMPLETION.md — 按 v0.9.0 重新评估得分

P1 (两周):
  □ TECHNICAL_ARCHITECTURE.md — 更新模块计数和技术栈
  □ DEPLOY_KYLIN — 补充实机验证 + FAQ
  □ deploy/loongarch_boot.sh — 新建麒麟一键启动脚本

P2 (一月):
  □ 所有文档统一 pre-commit hook 自动校验
  □ 一张架构全景图 (ASCII art 或 Mermaid)
```

---

## 三、5 个高价值创新方向

### 创新 1: Gitee Wiki 双向知识闭环

**现状**: 本地 Playbook(30+) + Gitee Wiki 单向拉取。Wiki push 标记为"待建"。  
**问题**: 知识只进不出 — 在系统中沉淀的知识无法反哺 Wiki。  
**方案**:
```
安全事件 → KnowledgeGuard.auto_extract() → 知识草稿
  → 人工审核 → approve → push 到 Gitee Wiki
  → Webhook → 其他节点自动拉取 → 知识同步
```
**价值**: 赛题"知识回流"得分点 + 多节点知识共享  
**工作量**: 3-5 天

### 创新 2: 麒麟 KYSEC 深度集成

**现状**: MAC checker 存在但为"检测模式"（enforce=True 但实际只告警）。  
**问题**: 未利用麒麟 KYSEC 的内核安全能力（三权分立、执行控制）。  
**方案**:
```
安全事件 → mac_checker → 自动生成 KYSEC 策略规则
  → 沙箱预演验证 → 安全工程师审批 → 写入 KYSEC 策略库
  → 系统进入 enforce 模式 → 实时拦截
```
**价值**: 麒麟赛题核心差异化 + 真正的 OS 级安全闭环  
**工作量**: 5-7 天

### 创新 3: 自适应告警阈值学习

**现状**: DynamicThreshold 用 mean+2.5*stddev，参数 2.5 是硬编码。  
**问题**: 不同主机/不同时段的正常基线不同，2.5 可能太松或太紧。  
**方案**:
```
历史告警数据 → 标注（真告警/误报）→ 训练二分类器
  → 输出自适应 k_factor → 周期性重训练
  → 效果: 误报率 -30%, 漏报率 -20%
```
**价值**: 告别硬编码阈值，真正"智能"运维  
**工作量**: 3-4 天

### 创新 4: 一键答辩包生成器

**现状**: 需要手动打包 tar.gz、手动写 README、手动准备演示脚本。  
**问题**: 答辩准备时间长（30min+），容易遗漏文件。  
**方案**:
```bash
python scripts/package_release.py --target kylin-loongarch
  → 自动打包: 源码 + dist + 文档 + 演示脚本 + 安装说明
  → 输出: dist/security-agent-v0.9.0-kylin-loongarch.tar.gz
  → 附带: 一键启动脚本 + 验证命令 + 演示路径
```
**价值**: 答辩/交付效率提升 10x  
**工作量**: 1-2 天

### 创新 5: 沙箱穿透自动化回归测试

**现状**: BoundaryFuzzer 有 7 种变异策略，但只跑一次，不持续。  
**问题**: 新代码可能引入沙箱穿透漏洞，但无人察觉。  
**方案**:
```bash
# 每天凌晨自动运行
python scripts/benchmark.py --fuzz-intensive
  → 1000 轮变异测试 → 对比上次结果
  → 新穿透 → P0 告警 + 自动创建 issue
  → 无新穿透 → 记录健康趋势
```
**价值**: 持续安全保障 + CI/CD 集成  
**工作量**: 2-3 天

---

## 四、v1.0 路线图

```
Phase 0 (本周) — 文档修复
  P0: 重写 frontend/ARCHITECTURE.md + REPO_STRUCTURE.md + A2_STANDARDS
  P0: 修正 gitignore → push GitHub + Gitee

Phase 1 (2 周) — 创新落地
  创新 1: Gitee Wiki 双向闭环
  创新 4: 一键答辩包生成器
  创新 5: 沙箱穿透回归测试

Phase 2 (3-4 周) — 深度创新
  创新 2: 麒麟 KYSEC 深度集成
  创新 3: 自适应告警阈值学习
  文档: 全部 pre-commit hook 自动化

Phase 3 (v1.0 发布)
  麒麟实机全链路验收
  答辩材料全套更新
  版本号 → 1.0.0
```

---

## 五、立即可行动项

```bash
# 1. 提交修正（移除大文件）
git rm --cached data/execution_learner.jsonl data/benchmark_history.jsonl data/.jwt_secret
git rm --cached -r data/knowledge_drafts/
git add .gitignore
git commit --amend --no-edit

# 2. 推送
git push origin master
git push gitee master

# 3. Wiki 同步
python security_agent/knowledge/gitee_wiki/sync.py  # 双向同步
```

---

*设计完成日期：2026-07-13 · 下一步：执行 Phase 0 文档修复*

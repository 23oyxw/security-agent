# A2 赛题作品提交 — 文档索引

> 第十五届中国软件杯 · A2 赛题 · 麒麟软件有限公司  
> 项目：security-agent v0.9.0  
> 提交日期：2026年7月

---

## 提交清单（9 项）

| 编号 | 赛题要求 | 对应文件 | 说明 |
|------|---------|---------|------|
| **1** | 软件功能需求分析文档 | [👉 打开](../architecture/EXPERIENCE_DRIVEN_DESIGN.md) | 体验驱动设计：用户场景→功能需求→接口契约 |
| **2** | 软件功能设计文档 | [👉 打开](../architecture/FINAL_ARCHITECTURE.md) | 终版架构：3 Agent + 5 层流水线 + 模块矩阵 |
| **3** | 软件产品说明书 | [👉 打开](../PRODUCT_MANUAL.md) | 产品定位、功能列表、运行环境、接口说明 |
| **4** | 软件功能测试报告 | [👉 打开](../FUNCTIONAL_TEST_REPORT.md) | 111 用例明细，7 模块逐项验收 |
| **5** | 软件性能测试报告 | [👉 打开](../PERFORMANCE_BENCHMARK.md) | 基准数据：耗时、吞吐、健康度趋势 |
| **6** | 安装包及部署文档 | [👉 打开](../DEPLOY_KYLIN_LOONGARCH.md) | 麒麟 LoongArch 部署指南（含依赖清单+权限说明） |
| **7** | 软件源代码压缩包 | `dist/security-agent-v0.9.0-*.tar.gz` | 2.4MB，`bash scripts/package-release.sh` 生成 |
| **8** | 演示 PPT | 📋 大纲：[👉 打开](../competitions/PPT_OUTLINE.md) | 15 页 · 7 分钟 |
| **9** | 演示视频 | 📋 脚本见 PPT 大纲 | ≤7 分钟 · .mp4 |

---

## 辅助文档（评审参考，非必提交）

| 文档 | 路径 |
|------|------|
| 技术架构总览 | [../architecture/TECHNICAL_ARCHITECTURE.md](../architecture/TECHNICAL_ARCHITECTURE.md) |
| 五层流水线架构 | [../architecture/FIVE_LAYER_PIPELINE.md](../architecture/FIVE_LAYER_PIPELINE.md) |
| 三方统一契约 | [../architecture/TRIPLE_UNIFY.md](../architecture/TRIPLE_UNIFY.md) |
| 总控计划 | [../architecture/MASTER_PLAN.md](../architecture/MASTER_PLAN.md) |
| A2 官方缺口分析 | [../competitions/A2_OFFICIAL_GAP_ANALYSIS.md](../competitions/A2_OFFICIAL_GAP_ANALYSIS.md) |
| A2 标准与完成度 | [../competitions/A2_STANDARDS_AND_COMPLETION.md](../competitions/A2_STANDARDS_AND_COMPLETION.md) |
| 麒麟依赖清单 | [../deploy/KYLIN_DEPENDENCIES.md](../deploy/KYLIN_DEPENDENCIES.md) |
| 麒麟权限指南 | [../deploy/KYLIN_PERMISSIONS.md](../deploy/KYLIN_PERMISSIONS.md) |
| 麒麟实机验收 | [../deploy/KYLIN_VERIFICATION.md](../deploy/KYLIN_VERIFICATION.md) |

---

## 自检清单

- [x] 1. 需求分析 — 包含用户场景、功能需求、接口契约
- [x] 2. 功能设计 — 包含架构图、模块清单、技术选型
- [x] 3. 产品说明书 — 包含产品定位、功能列表、运行环境
- [x] 4. 功能测试 — 111 用例明细表，7 模块逐项结果
- [x] 5. 性能测试 — 基准数据、健康度追踪
- [x] 6. 部署文档 — 麒麟 LoongArch 完整步骤 + 依赖清单
- [x] 7. 源代码包 — `dist/security-agent-v0.9.0-20260719.tar.gz`（2.4MB）
- [ ] 8. 演示 PPT — 大纲已出，待制作 PPTX
- [ ] 9. 演示视频 — 脚本已出，待录制（≤7 分钟）

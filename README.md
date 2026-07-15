# 银河麒麟智能安全运维 Agent

> A2 赛题 · v0.9.0 · 260 py / 34 模块  
> 🎯 **目标平台**：麒麟高级服务器 V11 · LoongArch  
> 📐 **方法**：[9 份规范文档](docs/INDEX.md) → 契约驱动 → AI 编码 → 自动校验

**答辩入口**：[docs/INDEX.md](docs/INDEX.md) | **提交清单**：[docs/competitions/SUBMISSION_CHECKLIST.md](docs/competitions/SUBMISSION_CHECKLIST.md) | **架构**：[FINAL_ARCHITECTURE.md](docs/architecture/FINAL_ARCHITECTURE.md)

## 快速开始

```bash
bash boot_start.sh                  # Linux (含麒麟 LoongArch)
START_WIN.bat                       # Windows
# → http://127.0.0.1:8900
# 登录: admin / admin123
```

## 核心能力

| 层 | 名称 | 关键实现 |
|----|------|---------|
| L1 | 多维感知 | 8 维仪表盘 + 边界对抗 (12 探针 + 7 策略 Fuzzer) + TF-IDF 知识检索 |
| L2 | 安全防护 | 三层防御 30/35/35 + 7 层沙箱 (OverlayFS+ns+seccomp+cgroup) + 5 层告警静噪 |
| L3 | 工具执行 | 17 Skills (四簇) + 能力装箱 (ToolBox+FlowBox+PluginBox) + 智能终端 |
| L4 | 审计追溯 | IncidentSpine 全链路 trace_id + append-only 卷宗 + Gitee Wiki 回流 |
| L5 | 量化迭代 | 六维指标 + 散点/热力/分布 + 策略反写 L1 |

## 架构

```
三 Agent: core_dispatch(L1+L3) + safety_sandbox(L2) + audit_iteration(L4+L5)
五层流水线: L1 → L2 → GATE → L3 → L4 → L5
153 API 路由 · 21 Vue3 页面 · 111 tests (100% pass)
```

## MCP 工具簇

| 簇 | 功能 | Skills |
|----|------|--------|
| metrics | 指标采集 | healthcheck, monitor, system_info, cpu_tuning |
| logs | 日志处理 | log_analyzer, audit, trace |
| repair | 故障修复 | security_hardening, system_cleanup, disk_manager, incident_responder, config_manager |
| dispatch | 资源调度 | network_ops, process, terminal, memory_priority |

## A2 得分

| 维度 | 权重 | 得分 |
|------|------|------|
| MCP 插件丰富度 | 25% | **24/25** |
| 安全校验能力 | 30% | **27/30** |
| 推理链路可追溯性 | 25% | **25/25** |
| 系统架构与创新 | 20% | **17/20** |
| **总分** | **100%** | **93/100** |

## 测试

```bash
python scripts/benchmark.py              # 全量基准 (111 tests, ~10s)
python scripts/check_version.py          # 版本一致性
python scripts/verify_triple_unify.py    # 三方统一漂移检测
bash scripts/demo_three_layer_defense.sh # 三层防御演示
```

## 文档

- [文档总索引](docs/INDEX.md) · [仓库结构](docs/REPO_STRUCTURE.md) · [版本发布](docs/RELEASE.md)
- [终版架构](docs/architecture/FINAL_ARCHITECTURE.md) · [五层流水线](docs/architecture/FIVE_LAYER_PIPELINE.md)
- [麒麟部署](docs/DEPLOY_KYLIN_LOONGARCH.md) · [Windows](docs/deploy/WINDOWS.md)
- [演示脚本](docs/competitions/DEMO_SCRIPT.md) · [提交清单](docs/competitions/SUBMISSION_CHECKLIST.md)
- [性能基准](docs/PERFORMANCE_BENCHMARK.md) 🆕

## 需求边界

| 不做 | 原因 |
|------|------|
| Dify / AIFlowy 集成 | P2 可选 |
| 麒麟上 LiteLLM Docker | 龙架构无镜像 |
| Streamlit 作主前端 | 以 Vue3 :8900 为准 |
| 麒麟上 `npm run build` | dist 从 x86 打包带走 |

---

**🛡️ 让安全运维更智能** · GitHub Actions: [![CI](https://github.com/23oyxw/security-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/23oyxw/security-agent/actions/workflows/ci.yml)

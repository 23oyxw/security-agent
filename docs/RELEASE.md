# 版本与发布结构

> VERSION 真源: 0.9.0

## 校验

```bash
python scripts/check_version.py
python scripts/e2e_api_smoke.py
python scripts/benchmark.py
```

## 启动

```bash
# Windows
START_WIN.bat

# Linux (Kylin V11 LoongArch)
bash scripts/boot_start_loongarch.sh
```

http://127.0.0.1:8900  admin/admin123

## v0.9.0 变更摘要

| 维度 | v0.8.0 | v0.9.0 |
|------|--------|--------|
| 模块数 | ~180 py | ~260 py |
| 测试 | 0 | 94 (benchmark) |
| 沙箱 | 无 | 7 层隔离 (OverlayFS+ns+seccomp+cgroup) |
| 告警 | 原始通知 | 5 层静噪 (filter→dedup→throttle→correlation→escalation) |
| 终端 | 直接执行 | 5 阶段智能流水线 (context→pre_analyze→execute→post_verify→learn) |
| 文档激活 | 无 | TF-IDF 双索引 (BM25+余弦) |
| 边界韧性 | 无 | 12 探针 + 7 变异策略 Fuzzer |
| 知识自愈 | 无 | 一致性检查 + 新鲜度 + 休眠检测 |
| 能力装箱 | 分散 5 入口 | CapabilityRegistry 统一 (ToolBox+FlowBox+PluginBox) |
| 前端 | Streamlit | Vue3 (29 文件 px→rem) |
| Wiki | 无 | Gitee Wiki 10 页知识库 |

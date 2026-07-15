# 系统性能基准报告

> v0.9.0 · Windows 11 x86_64 开发机 · 2026-07-15
> 麒麟 LoongArch 数据待实机采集后追加

## 测试环境

| 项目 | 值 |
|------|-----|
| OS | Windows 11 Pro for Workstations 10.0.22000 |
| CPU | x86_64 |
| Python | 3.10.11 |
| pytest | 9.1.1 |
| 测试时间 | 2026-07-15 |

## 全量测试结果

```
总套件: 7 (v0.9.0 六大 Step + 三层防御)
总用例: 111
通过:   111
失败:   0
耗时:   9.59s
```

## 各套件明细

| 套件 | 用例数 | 描述 | 状态 |
|------|--------|------|------|
| sandbox | 19 | 全域沙箱透明化 (OverlayFS+namespace+session) | ✅ |
| alerts | 24 | 告警安静化 (throttle+floating+pipeline) | ✅ |
| document | 23 | 文档活化 (parser+chunker+embedder+indexer+pipeline) | ✅ |
| boundary | 16 | 边界自检化 (12 probes + 7 fuzzer strategies) | ✅ |
| capability | 12 | 能力装箱 (guard+toolbox+flowbox+pluginbox) | ✅ |
| knowledge | 15 | 知识自愈 (guard+freshness) | ✅ |
| three_layer | 2 | 三层防御端到端 | ✅ |

## 性能指标

| 指标 | 值 |
|------|-----|
| 平均每用例耗时 | 86ms |
| 最慢套件 | alerts (24 cases) |
| 内存占用 (pytest 进程) | ~120MB |
| 前端构建 (Vite) | 16.9s |
| 后端启动 (uvicorn) | <2s |
| API 响应 (health) | <5ms |
| API 响应 (defense/evaluate) | ~6ms |

## 健康度追踪

| 日期 | 用例数 | 通过 | 健康度 |
|------|--------|------|--------|
| 2026-07-15 | 111 | 111 | **100/100** |

## 已知局限

- `test_terminal_context.py` (28 cases) 在 Windows 上因 subprocess-in-subprocess 超时 (600s)，未纳入本次基准
- 该套件在 Linux 环境下预期正常通过
- GBK 编码警告仅在 Windows 中文环境出现，不影响测试结果

## 麒麟 LoongArch 待采集

- [ ] 全量 benchmark 在龙架构上运行
- [ ] CPU/内存/磁盘 I/O 对比基线
- [ ] API 响应延迟对比 (x86 vs LoongArch)
- [ ] KYSEC enforce 模式兼容性

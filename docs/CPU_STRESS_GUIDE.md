# CPU 压测工具使用指南

## 概述

项目提供了一套完整的 CPU 压测工具，支持单核/多核模式，自动生成 HTML 报告，并支持进程清理。

## 脚本清单

| 脚本 | 用途 | 兼容性 |
|------|------|--------|
| `stress_cpu.sh` | 主脚本，支持单核/多核压测 | ✅ 推荐使用 |
| `trigger_high_cpu.sh` | 单核压测快捷方式（向后兼容） | ✅ 保留 |
| `stress_cpu_test.sh` | 单核压测快捷方式（向后兼容） | ✅ 保留 |
| `cleanup_stress.sh` | 清理所有压测进程 | ✅ 增强版 |
| `cpu_report.py` | 生成 HTML/JSON 报告 | ✅ 增强版 |

## 使用方法

### 1. 快速压测（单核，5秒）

```bash
bash scripts/stress_cpu.sh
```

### 2. 多核压测（使用所有 CPU 核心）

```bash
bash scripts/stress_cpu.sh --multi
# 或指定时长
bash scripts/stress_cpu.sh --multi --duration 30
```

### 3. 仅生成报告（不压测）

```bash
bash scripts/stress_cpu.sh --report-only
```

### 4. 使用 stress 工具（更精确的压测）

```bash
# 先安装 stress
sudo apt-get install stress  # Debian/Ubuntu
sudo yum install stress      # RHEL/CentOS

# 使用 stress 进行多核压测
bash scripts/stress_cpu.sh --multi --use-stress
```

### 5. 清理残留进程

```bash
bash scripts/cleanup_stress.sh
```

## 参数说明

```
stress_cpu.sh [选项]

选项：
  -m, --multi          多核压测模式（使用所有 CPU 核心）
  -d, --duration N     压测时长（秒），默认 5 秒
  -r, --report-only    只生成报告，不启动压测
  -s, --use-stress     使用 stress 工具（如果可用）
  -q, --quiet          安静模式，减少输出
  -h, --help           显示帮助
```

## 报告内容

生成的 HTML 报告包含：

1. **全局 CPU 使用率** — 系统整体 CPU 占用
2. **各核心使用率详情** — 可视化展示每个 CPU 核心的实时使用率
3. **Top 15 进程** — 按 CPU 占用排序，包含进程名、用户、CPU%、内存%
4. **压测模式检测** — 自动识别当前是否处于压测状态
5. **负载平均值** — 1分钟、5分钟、15分钟负载

## UI 界面操作

在「系统监控」页面：

- **🔥 单核压测 (5秒)** — 快速压测单个 CPU 核心
- **🔥🔥 多核压测 (10秒)** — 压测所有 CPU 核心
- **🧹 清理压测残留进程** — 一键清理所有压测进程

## 向后兼容

旧脚本 `trigger_high_cpu.sh` 和 `stress_cpu_test.sh` 仍可使用，它们会转发到新脚本：

```bash
# 旧调用方式（仍可用）
bash scripts/trigger_high_cpu.sh    # 等效于 stress_cpu.sh --duration 5
bash scripts/stress_cpu_test.sh     # 等效于 stress_cpu.sh --duration 15
```

## 故障排查

### 问题：找不到 dd 命令
```bash
# Debian/Ubuntu
sudo apt-get install coreutils

# RHEL/CentOS
sudo yum install coreutils
```

### 问题：找不到 uv 命令
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 问题：压测进程卡住
```bash
# 强制清理
bash scripts/cleanup_stress.sh

# 或手动清理
pkill -9 -f "dd if=/dev/zero"
pkill -9 stress
```

### 问题：权限不足
某些系统可能需要 sudo 才能查看所有进程：
```bash
sudo bash scripts/stress_cpu.sh --multi
```

## 技术细节

### 压测原理

- **单核模式**：启动 1 个 `dd if=/dev/zero of=/dev/null` 进程
- **多核模式**：启动 N 个 dd 进程（N = CPU 核心数）
- **stress 模式**：使用 `stress --cpu N` 工具（更精确）

### 安全机制

1. 自动清理 — 脚本退出时自动终止所有压测进程（通过 `trap EXIT`）
2. 兜底清理 — 脚本启动前自动清理残留进程
3. 超时机制 — UI 调用时设置 60 秒超时
4. 进程隔离 — 使用 `pkill -f` 精确匹配压测进程，避免误杀

## 示例输出

```
========================================
  🔧 CPU 压测工具 v2.0
========================================

[INFO] 检查依赖...
[INFO] 清理之前的压测进程...
[INFO] 启动 CPU 压测...
[INFO]   模式: 多核 (8 核心)
[INFO]   时长: 10 秒
[INFO]   工具: dd
[INFO]   CPU: Intel(R) Core(TM) i7-9700K CPU @ 3.60GHz
[INFO]   已启动 8 个 dd 进程: 1234 1235 1236 1237 1238 1239 1240 1241
[INFO] 等待 5 秒让 CPU 升温...
[INFO] 采集 CPU 快照并生成 HTML 报告...
[cpu_report] 已生成: /path/to/data/reports/cpu_report_20260521_072500.html
[INFO] 停止压测进程...

========================================
[OK] 压测完成！
========================================

📋 报告位置: /path/to/data/reports/cpu_report_*.html
   用浏览器打开即可查看 CPU 快照

💡 提示:
   - 多核压测: bash scripts/stress_cpu.sh --multi
   - 仅看报告: bash scripts/stress_cpu.sh --report-only
   - 清理残留: bash scripts/cleanup_stress.sh
========================================
```

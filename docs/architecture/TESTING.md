# CPU 阈值测试指南

> 本文档覆盖三种 CPU 阈值测试方式，从一键快照到完整 P2 监控验收，满足不同场景需求。

---

## 方式一：一键快照（最快）

单条命令，不需要启动 UI、不需要压测，立即生成当前 CPU 状态的 HTML 报告。

```bash
uv run python scripts/cpu_report.py
```

**输出**：`data/reports/cpu_report_时间戳.html`，直接用浏览器打开即可查看：
- 当前系统 CPU 使用率
- 负载平均值（1/5/15 分钟）
- Top 10 进程（按 CPU 排序，带 CPU 进度条）

**适用场景**：日常快速查看、系统健康巡检、报告存档。

---

## 方式二：一键压测 + 报告（自动化模拟）

一条命令自动完成：压高 CPU → 等几秒 → 采集快照 → 出报告 → 自动清理。

### 脚本 A — `trigger_high_cpu.sh`（通用触发）

```bash
bash scripts/trigger_high_cpu.sh
```

流程：
1. 启动 `dd if=/dev/zero of=/dev/null bs=1M` 压 CPU（后台）
2. 等待 5 秒让 CPU 上升
3. 运行 `cpu_report.py` 生成带高负载快照的 HTML 报告
4. 自动终止 dd 压测进程

### 脚本 B — `stress_cpu_test.sh`（更详细的输出）

```bash
bash scripts/stress_cpu_test.sh
```

与 A 相同逻辑，但输出步骤标注更清晰（1/4 → 4/4），方便看执行进度。

**适用场景**：
- 验证 CPU 报告在高负载下的表现
- 快速模拟告警触发条件
- 给非技术人员演示用的「一键压测」

---

## 方式三：完整监控阈值验收（最完整）

完整走一遍 P2 实时监控的 CPU 阈值检测流程，验证从压测到告警的全链路。

### 前置条件

- Streamlit 应用正常运行（`boot_start.sh` 或 `uv run streamlit run streamlit_app.py`）
- 本机可以打开浏览器访问 `http://127.0.0.1:8501`

### 操作步骤

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| **1** | 打开浏览器进入 Streamlit 控制台 | 首页正常加载 |
| **2** | 左侧栏点击 **「启动监控」** | 提示「监控已启动」，事件列表出现 "监控启动" 事件 |
| **3** | 切换到 **「系统监控」** 页面 | 看到进程列表、事件流开始滚动 |
| **4** | **另开一个终端**，运行 CPU 压测：<br>`dd if=/dev/zero of=/dev/null bs=1M &` | CPU 快速上升（可用 `top` 或 `htop` 确认） |
| **5** | 切回 **「系统监控」** 页面，观察事件列表 | 出现 **"CPU 占用过高"** 高等级事件，内容包含当前 CPU 百分比 |
| **6** | 查看 **「告警」** 侧栏小红点或告警页面 | 告警计数增加 |
| **7** | 停止压测：<br>`kill %1` 或 `pkill -f "dd if=/dev/zero"` | CPU 回落，告警事件不再新增 |
| **8** | 左侧栏点击 **「停止监控」** | 提示「监控已停止」 |

### 阈值说明

监控 CPU 阈值定义在 `security_agent/monitor/service.py`：

```python
@dataclass
class MonitorService:
    cpu_threshold: float = 80.0   # 默认 80%
```

- 当系统 CPU 超过 80%，触发 `"CPU 占用过高"` 高等级事件
- 事件进入 `_events` 队列（最多保留 500 条）
- 同时通过 `publish_monitor_event` 推送到告警通道
- 高等级事件自动进入升级策略引擎（`EscalationEngine.process_event`）

如需修改阈值，可在 `.env` 中暂不支持直接配置，需要改 `service.py` 中的 `cpu_threshold` 值。

---

## 三种方式对比

| 方式 | 命令/操作 | 耗时 | 依赖 | 验证目标 |
|------|----------|------|------|---------|
| ① 一键快照 | `uv run python scripts/cpu_report.py` | ~2 秒 | 无 | 当前 CPU 快照 |
| ② 一键压测+报告 | `bash scripts/trigger_high_cpu.sh` | ~15 秒 | 无 | 高负载下的快照 |
| ③ 完整监控验收 | Streamlit UI + 手动 dd | ~30 秒 | 浏览器 | P2 全链路告警 |

---

## 常见问题

### Q: 脚本报 `command not found: uv`
需要先安装 uv 包管理器：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# 或：pip install uv
```

### Q: dd 压测 CPU 上不去
- 检查系统是否有其他进程限制 CPU（如 `cpulimit`、cgroup）
- 多核机器可以多开几个 dd：`for i in $(seq 1 4); do dd if=/dev/zero of=/dev/null bs=1M & done`
- 或改用 `stress` 工具（需安装）：`apt install stress && stress -c 4 --timeout 30`

### Q: 监控启动后没有告警事件
- 确认左侧栏显示的是「停止监控」（表示已启动）
- 确认 dd 压测确实在执行（`top -b -n1 | grep dd`）
- 阈值默认 80%，如果 CPU 没到 80% 不会触发
- 检查 `.env` 中 `MONITOR_*` 相关配置是否关闭

### Q: 如何查看历史 CPU 趋势？
当前版本提供快照模式报告。如需连续趋势，可在「系统监控」页启动监控后观察事件流，或者通过 Skill 的 `health_trend` 工具查询历史数据。
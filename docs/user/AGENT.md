# Agent 说明 v0.4.1

> 白话版见 [PLAIN_GUIDE.md](PLAIN_GUIDE.md)

## 自动化等级：L3

| 动作 | 是否自动 |
|------|----------|
| 扫描、列进程、看端口、读审计、知识库检索 | ✅ 自动 |
| 白名单终端（`ps`、`ss`、`grep` 等） | ✅ 自动 |
| `kill` / `pkill` / `sudo` 写操作 | ❌ 须 UI 勾选确认 |
| `rm -rf`、管道 `bash` 等 | ❌ 代码直接拒绝 |
| 回答内容 | 须引用工具结果或知识库 `PB-*`，禁止编造 |

## 两个 Agent 入口

| Agent | 页面 | 适合 |
|-------|------|------|
| `AgentBrain` | 智能助手 | 问答、多轮查数据 |
| `AutonomousAgent` | 自主运维 | 输入一个目标，自动多步执行 |

## 知识检索（防幻觉）

```text
用户问题 → 检索 31 条剧本 → 注入 LLM → 调工具拿真实数据 → 结构化建议
```

相关工具：`search_security_knowledge`、`get_grounded_advice`、`build_knowledge_index`（可选向量）

## 风险评级标准（扫描 / 监控 / 策略）

五级枚举见 `security_agent/agent/policy.py` 的 `RiskLevel`：

| 等级 | 典型触发（代码规则） |
|------|----------------------|
| **严重** | 进程名/命令行命中 `HIGH_RISK_PROCESS_NAMES` 或 `HIGH_RISK_CMD_PATTERNS`（如 `nc`、`nmap`、`| bash`、`rm -rf /`） |
| **高** | 敏感路径（`/etc/shadow` 等）对非 root 可写；监控：新增监听且为 `EXPOSED_RISKY_PORTS` + `0.0.0.0` 绑定 |
| **中** | 未匹配到上级的默认归类；部分监控事件 |
| **低 / 信息** | 监控启动、一般进程快照等 |

**策略层**（`policy.py`）：`严重`/`高` 触发 `should_auto_warn`（界面提示，**不自动杀进程**）；`auto_block` 恒为 `False`。  
**校准**：66 条检测 fixture 只验证「是否应报风险」（二分类），不单独校准等级字符串。

## 规则（代码级，不可绕过）

实现：`security_agent/rules/engine.py`  
终端执行：`security_agent/terminal/executor.py`

## 启动

```bash
bash boot_start.sh
```

# 离屏告警、终端监视与 MCP

## 你在终端操作、Web 在后台 — 怎么收到告警？

控制台（Streamlit）在后台运行时，**浏览器里的事件表你看不到**。系统会用 **三条通道** 提醒你：

| 通道 | 说明 | 适用场景 |
|------|------|----------|
| **桌面通知** | `notify-send`（银河麒麟/UKUI 通知中心） | 你在桌面做别的事 |
| **告警文件** | `data/alerts/events.jsonl`、`alerts.log` | 脚本、日志采集、事后审计 |
| **终端监视** | `uv run python scripts/alert_watch.py` | 你开着普通用户终端干活 |

触发条件（默认）：监控事件等级为 **严重** 或 **高**（如高危新进程、敏感文件变更、登录失败、高危端口监听等）。  
普通「新进程」「心跳」不会弹窗，避免刷屏。

### 推荐用法（两个终端）

```bash
# 终端 1：后台 Web + 监控
cd /home/oy0/security-agent
bash boot_start.sh
# 在浏览器里点「启动监控」

# 终端 2：普通用户即可，实时看告警
cd /home/oy0/security-agent
uv run python scripts/alert_watch.py
```

关闭桌面弹窗：在 `.env` 中设置 `NOTIFY_DESKTOP=false`，仍写入 `data/alerts/`。

---

## MCP 能连「本地终端」吗？

**MCP 不是 SSH，也不会自动占用你当前的 bash 会话。**

| 能力 | MCP / 本项目 |
|------|----------------|
| 暴露扫描、监控、知识库等 **工具** | 是，`security_agent/mcp/server.py`（stdio） |
| 在 Cursor / IDE 里调用同一套工具 | 是，配置 MCP Server |
| 替代你手动 `source .venv` | **不需要**，用 `uv run` 即可 |
| 任意 shell 命令（无限制） | **否**，终端走白名单 + 规则引擎 |
| 全自动杀进程 | **否**，须 UI/用户确认 |

### Cursor MCP 配置示例

```json
{
  "mcpServers": {
    "security-agent": {
      "command": "uv",
      "args": ["run", "python", "-m", "security_agent.mcp.server"],
      "cwd": "/home/oy0/security-agent"
    }
  }
}
```

### 终端对话（不用 MCP）

```bash
cd /home/oy0/security-agent
uv run python cli.py          # 本地工具，低延迟
uv run python cli.py --mcp    # 经 MCP Server 调工具（一般不必）
```

### 「全方位防护」建议组合

1. **Web 后台**：`boot_start.sh` + 启动监控 + 自动刷新  
2. **终端监视**：`alert_watch.py` 常开  
3. **IDE**：MCP 让 Agent 调扫描/端口/知识库，不编造数据  
4. **自主运维页**：白名单终端 + 勾选确认后执行 `kill`/`sudo`  
5. **非 root 日常**：普通用户跑控制台即可；拦截他人进程需 root 启动或 `sudo kill`

虚拟环境 **不必手动 activate**：项目统一 `uv run …`，与 MCP、Streamlit、脚本一致。

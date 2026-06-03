# MCP 服务：读写策略与成本模型

## 概述

本文档说明 MCP 独立服务的**读写安全策略**和**成本追踪**机制。

---

## 一、读写策略

### 1. 工具分类

所有 MCP 工具按**读写属性**分为两类：

| 类型 | 说明 | 默认策略 |
|------|------|----------|
| **🔍 只读工具** | 仅查询、分析、快照，不修改系统 | 可直接调用 |
| **✏️ 写入工具** | 修改系统状态（删除、重启、修改配置） | **需要确认** |

### 2. 各服务工具分类

#### healthcheck（健康巡检）- 全部只读
| 工具 | 操作 | 风险 |
|------|------|------|
| `health_full_check` | 读取系统指标 | 无 |
| `health_trend` | 分析历史数据 | 无 |
| `health_threshold_check` | 对比阈值 | 无 |
| `health_disk_analysis` | 读取磁盘信息 | 无 |
| `health_network_analysis` | 读取连接状态 | 无 |
| `health_get_history` | 读取历史记录 | 无 |

#### log_analyzer（日志分析）- 全部只读
| 工具 | 操作 | 风险 |
|------|------|------|
| `log_scan` | 读取日志文件 | 无 |
| `log_tail` | 读取日志尾部 | 无 |
| `log_search` | 搜索日志内容 | 无 |
| `log_patterns` | 返回模式列表 | 无 |
| `log_recent_matches` | 返回匹配记录 | 无 |
| `log_incremental_scan` | 增量读取 | 无 |

#### config_manager（配置管理）- 全部只读
| 工具 | 操作 | 风险 |
|------|------|------|
| `config_snapshot` | 生成快照（只读+存储） | 低 |
| `config_diff` | 对比差异 | 无 |
| `config_history` | 查询历史 | 无 |
| `config_audit` | 审计状态 | 无 |
| `config_add_watch` | 添加监控项（仅内存） | 低 |

> **运维规则**: 配置管理仅做快照和检测，**不自动修改任何配置文件**

#### security_hardening（安全加固）- 全部只读
| 工具 | 操作 | 风险 |
|------|------|------|
| `hardening_ssh_audit` | 读取配置 | 无 |
| `hardening_firewall_audit` | 读取规则 | 无 |
| `hardening_vulnerability_scan` | 扫描文件 | 无 |
| `hardening_baseline_check` | 检查合规 | 无 |
| `hardening_full_scan` | 综合扫描 | 无 |

#### incident_responder（故障响应）- 含写入操作
| 工具 | 操作 | 风险 | 需要确认 |
|------|------|------|----------|
| `incident_diagnose` | 诊断分析 | 无 | 否 |
| `incident_self_heal` | **执行清理命令** | 低-中 | **是** |
| `incident_list_scripts` | 列出脚本 | 无 | 否 |
| `incident_response_plan` | 生成计划 | 无 | 否 |

**`incident_self_heal` 可执行的操作：**
- ✅ `clear_tmp`: 删除 /tmp 下 7 天以上的文件
- ✅ `rotate_logs`: 清理 journal 日志到 200MB
- ✅ `clear_cache`: 清理 apt 包缓存
- ❌ `restart_nginx`: 重启服务（不允许自动执行）
- ❌ `restart_docker`: 重启服务（不允许自动执行）

### 3. 安全机制

```python
# MCP Client 调用示例
from security_agent.skills.mcp_client import MCPClientManager

manager = MCPClientManager()

# 1. 检查工具读写属性
info = manager.check_read_only("incident_responder", "incident_self_heal")
# {
#   "known": True,
#   "read_only": False,
#   "requires_confirmation": True,
#   "warning": "此工具可能修改系统状态"
# }

# 2. 调用时强制确认（写入工具）
async def confirm_callback(service, tool, args):
    # 这里可以弹窗、记录日志、等待用户输入
    return await user_confirm(f"{service}/{tool} 将执行: {args}")

result = await manager.call_tool_with_confirm(
    "incident_responder",
    "incident_self_heal",
    {"script_id": "clear_tmp"},
    confirm_callback=confirm_callback
)
```

---

## 二、成本模型

### 1. 成本分类

| 成本类型 | 计费单元 | 说明 |
|----------|----------|------|
| **MCP 调用** | 按调用次数 | 工具执行成本 |
| **LLM 推理** | 按 token | AI 分析、总结成本 |
| **外部 API** | 按调用/流量 | 第三方服务成本 |

### 2. MCP 调用成本预估

基于操作复杂度估算（仅供参考）：

| 工具类型 | 预估成本 | 说明 |
|----------|----------|------|
| 简单查询 | 0.1 分/次 | 如 `health_threshold_check` |
| 扫描分析 | 0.3-0.5 分/次 | 如 `log_scan`, `hardening_full_scan` |
| 复杂诊断 | 0.5-1.0 分/次 | 如 `incident_diagnose` |
| 写入操作 | 0.5 分/次 | 如 `incident_self_heal` |

### 3. LLM 推理成本

使用模型与成本对比：

| 模型 | 用途 | 相对成本 | 估算价格 |
|------|------|----------|----------|
| `deepseek-v4-pro` | 复杂推理、工具调用 | 高 | ~4 元/百万 tokens |
| `deepseek-v4-flash` | 批量分析、总结 | 低 | ~1 元/百万 tokens |
| `mimo-v2.5-pro` | 通用任务 | 中 | ~2 元/百万 tokens |

### 4. 成本追踪 API

```python
from security_agent.skills.mcp_client import MCPClientManager

manager = MCPClientManager()

# 执行多次调用...

# 获取成本统计
summary = manager.get_cost_summary()
# {
#   "total_calls": 150,
#   "total_cost": 45.5,  # 分
#   "avg_cost_per_call": 0.303,
#   "by_service": {
#     "healthcheck": {"calls": 60, "cost": 12.0},
#     "log_analyzer": {"calls": 50, "cost": 20.0},
#     "incident_responder": {"calls": 40, "cost": 13.5}
#   },
#   "by_tool": {
#     "healthcheck/health_full_check": {"calls": 60, "cost": 12.0},
#     "log_analyzer/log_scan": {"calls": 50, "cost": 20.0}
#   }
# }

# 获取详细记录
recent = manager.get_recent_calls(limit=10)
for r in recent:
    print(f"{r['timestamp']}: {r['service']}/{r['tool']} "
          f"cost={r['cost']} duration={r['duration_ms']}ms")

# 清空调用历史
manager.clear_history()
```

### 5. 预算控制建议

```python
# 设置每日预算上限
DAILY_BUDGET_CENTS = 1000  # 10 元/天

async def call_with_budget(manager, service, tool, args):
    summary = manager.get_cost_summary()
    if summary["total_cost"] >= DAILY_BUDGET_CENTS:
        raise BudgetExceededError(f"今日预算已用完: {summary['total_cost']} 分")
    
    return await manager.call_tool(service, tool, args)
```

---

## 三、最佳实践

### 1. 生产环境部署

```python
# 只连接必要的服务
from security_agent.skills.mcp_client import quick_connect_all

# 仅启用只读服务
READONLY_SERVICES = {
    "healthcheck": ("127.0.0.1", 8081),
    "log_analyzer": ("127.0.0.1", 8082),
    "config_manager": ("127.0.0.1", 8083),
    "security_hardening": ("127.0.0.1", 8084),
    # incident_responder 单独管理，需要确认
}

manager = await quick_connect_all(READONLY_SERVICES)
```

### 2. 写入操作审计

```python
# 所有写入操作必须记录审计日志
async def audited_call(manager, service, tool, args, user):
    # 1. 检查是否为写入操作
    info = manager.check_read_only(service, tool)
    if not info["read_only"]:
        audit_log.record({
            "type": "mcp_write",
            "user": user,
            "service": service,
            "tool": tool,
            "args": args,
            "timestamp": now_iso(),
        })
    
    # 2. 执行调用
    return await manager.call_tool(service, tool, args)
```

### 3. 批量任务成本优化

```python
from security_agent.agent.budget import get_budget_agent

# 批量日志分析使用低成本模型
budget_agent = get_budget_agent()

# 使用 BudgetAgent 进行批量分析（deepseek-v4-flash）
result = budget_agent.summarize_logs(matches, max_entries=100)
```

---

## 四、总结

| 维度 | 策略 |
|------|------|
| **读/写分离** | 5个服务中，4个完全只读；1个含写入，强制确认 |
| **安全默认** | 写入工具默认需要 confirmation callback |
| **成本透明** | 每次调用自动记录成本，支持按服务/工具统计 |
| **预算可控** | 支持设置预算上限，超限自动拒绝 |

**运维规则重申**：
- 配置管理仅做快照和检测，不自动修改任何配置文件
- 配置变更建议需说明影响范围，涉及系统配置必须人工确认
- 自愈操作仅限低风险（清理临时文件、日志轮转），高风险操作需人工确认

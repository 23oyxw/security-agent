# MCP 独立服务架构

## 概述

每个 Skill 现在是一个**独立的 MCP Server**，可以单独启动、单独测试、独立部署。

```
┌─────────────────────────────────────────────────────────┐
│                    Agent / UI / CLI                      │
│                   (MCP Client 调用)                       │
└─────────────────────────────────────────────────────────┘
                           │ MCP 协议 (stdio / HTTP)
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐      ┌──────▼─────┐     ┌─────▼────┐
   │healthcheck│    │log_analyzer│     │config_mgr│
   │  :8081   │    │   :8082    │     │  :8083   │
   └──────────┘    └────────────┘     └──────────┘
        │                  │                  │
   ┌────▼────┐      ┌──────▼─────┐
   │ sec_hard │    │incident_rsp│
   │  :8084   │    │   :8085    │
   └──────────┘    └────────────┘
```

## 快速开始

### 1. 查看所有服务

```bash
python -m security_agent.skills.launcher --list
```

输出：
```
可用 MCP 服务列表:
------------------------------------------------------------
  healthcheck          : 健康巡检 (默认端口 8081)
  log_analyzer         : 日志分析 (默认端口 8082)
  config_manager       : 配置管理 (默认端口 8083)
  security_hardening   : 安全加固 (默认端口 8084)
  incident_responder   : 故障响应 (默认端口 8085)
------------------------------------------------------------
```

### 2. 查看单个服务信息

```bash
python -m security_agent.skills.launcher healthcheck --info
```

### 3. 启动单个服务（stdio 模式，适合本地 Agent）

```bash
# 前台运行，Ctrl+C 停止
python -m security_agent.skills.launcher healthcheck
```

### 4. 启动单个服务（HTTP 模式，适合远程调用）

```bash
# HTTP 模式，指定端口
python -m security_agent.skills.launcher healthcheck --transport http --port 8081

# 测试服务
http://127.0.0.1:8081/info
```

### 5. 后台启动所有服务

```bash
python -m security_agent.skills.launcher --all --transport http
```

验证：
```bash
# 检查所有服务
for port in 8081 8082 8083 8084 8085; do
    echo "Port $port:"
    curl -s http://127.0.0.1:$port/info | head -10
done
```

停止所有：
```bash
pkill -f 'mcp_server'
```

---

## 服务详情

### 1. healthcheck (健康巡检)

**端口**: 8081

**工具**:
| 工具名 | 描述 |
|--------|------|
| health_full_check | 全面健康巡检：CPU/内存/磁盘/网络/负载/运行时间 |
| health_trend | 趋势分析（含预测） |
| health_threshold_check | 阈值检查 |
| health_disk_analysis | 磁盘使用分析 |
| health_network_analysis | 网络连接分析 |
| health_get_history | 获取历史数据 |

**测试**:
```bash
python -m security_agent.skills.healthcheck.mcp_server --info
python -m security_agent.skills.healthcheck.mcp_server --transport http
```

### 2. log_analyzer (日志分析)

**端口**: 8082

**工具**:
| 工具名 | 描述 |
|--------|------|
| log_scan | 扫描所有日志源，检测10种异常模式 |
| log_tail | 实时跟踪日志尾部 |
| log_search | 关键词搜索 |
| log_patterns | 获取支持的异常模式列表 |
| log_recent_matches | 获取最近匹配记录 |
| log_incremental_scan | 增量扫描 |

### 3. config_manager (配置管理)

**端口**: 8083

**工具**:
| 工具名 | 描述 |
|--------|------|
| config_snapshot | 生成配置文件快照 |
| config_diff | 对比配置差异 |
| config_history | 查看变更历史 |
| config_audit | 审计配置状态 |
| config_add_watch | 添加监控文件 |

### 4. security_hardening (安全加固)

**端口**: 8084

**工具**:
| 工具名 | 描述 |
|--------|------|
| hardening_ssh_audit | SSH配置审计 |
| hardening_firewall_audit | 防火墙审计 |
| hardening_vulnerability_scan | 漏洞扫描 |
| hardening_baseline_check | CIS基线检查 |
| hardening_full_scan | 完整扫描 |

### 5. incident_responder (故障响应)

**端口**: 8085

**工具**:
| 工具名 | 描述 | 需确认 |
|--------|------|--------|
| incident_diagnose | 故障诊断 | 否 |
| incident_self_heal | 执行自愈脚本 | **是** |
| incident_list_scripts | 列出自愈脚本 | 否 |
| incident_response_plan | 生成响应计划 | 否 |

---

## 独立测试方法

### 测试 healthcheck

```bash
# 1. 启动服务（HTTP模式方便测试）
python -m security_agent.skills.healthcheck.mcp_server --transport http --port 8081

# 2. 查看服务信息
curl http://127.0.0.1:8081/info

# 3. 使用 MCP 客户端测试（需要单独的测试脚本）
```

### 使用 stdio 模式测试

```bash
# 直接运行，通过 stdin 输入 MCP 协议消息
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | \
    python -m security_agent.skills.healthcheck.mcp_server
```

---

## 架构对比

### 旧模式（零散）

```python
# 所有工具在一个注册表
TOOL_REGISTRY = {
    "health_full_check": (...),
    "log_scan": (...),
    "config_snapshot": (...),
    # 全部混在一起
}
```

**问题**:
- 无法单独测试某个 Skill
- 无法独立部署
- 耦合在一起

### 新模式（独立 MCP）

```python
# 每个 Skill 是独立进程
healthcheck/          # 独立服务
  └── mcp_server.py   # 6个工具

log_analyzer/         # 独立服务
  └── mcp_server.py   # 6个工具

config_manager/       # 独立服务
  └── mcp_server.py   # 5个工具
```

**优势**:
- ✅ 每个 Skill 可独立启动/停止
- ✅ 可独立测试（`python -m xxx.mcp_server --info`）
- ✅ 可独立部署（不同机器、不同容器）
- ✅ 符合 MCP 协议标准
- ✅ 支持 stdio 和 HTTP 两种模式

---

## 部署场景

### 场景1: 单机本地（开发测试）

```bash
# 使用 stdio 模式，Agent 直接调用
python -m security_agent.skills.launcher healthcheck
```

### 场景2: 单机多服务（生产）

```bash
# 后台启动所有服务
python -m security_agent.skills.launcher --all --transport http

# Agent 配置 MCP endpoints:
# healthcheck: http://127.0.0.1:8081
# log_analyzer: http://127.0.0.1:8082
# ...
```

### 场景3: 多机分布式（大规模）

```bash
# 机器A: 运行 healthcheck + log_analyzer
python -m security_agent.skills.launcher healthcheck -t http -p 8081 -H 0.0.0.0
python -m security_agent.skills.launcher log_analyzer -t http -p 8082 -H 0.0.0.0

# 机器B: 运行 config_manager + security_hardening
python -m security_agent.skills.launcher config_manager -t http -p 8083 -H 0.0.0.0
python -m security_agent.skills.launcher security_hardening -t http -p 8084 -H 0.0.0.0
```

---

## A2 赛题对应

| 赛题要求 | 实现方式 |
|---------|---------|
| **MCP协议插件化** | 每个 Skill 是独立 MCP Server |
| **可插拔架构** | 独立进程，独立部署 |
| **工具封装** | 每个 Skill 5-6 个 MCP 工具 |
| **独立测试** | `python -m xxx.mcp_server --info` |

---

## 下一步（可选）

1. **UI 集成**: 更新 Skill 插件页，支持连接独立 MCP 服务
2. **Agent 集成**: Brain 通过 MCP client 调用独立服务
3. **容器化**: 每个 MCP Server 打成独立 Docker 镜像
4. **服务发现**: 添加注册中心，动态发现 MCP 服务

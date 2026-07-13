# A2 赛题 — 核心痛点解决方案 & 架构决策（历史归档）

> 生成时间: 2026-05-22 · ⚠️ **已归档**：当前架构决策以 **[FINAL_ARCHITECTURE.md](../architecture/FINAL_ARCHITECTURE.md)** 为准。

---

## 一、关于微服务架构：不需要

### 结论：当前单体模块化架构已经符合赛题要求，不需要引入微服务。

**理由：**

| 维度 | 赛题要求 | 当前实现 | 微服务必要性 |
|------|---------|---------|------------|
| 部署环境 | 单机 LoongArch + 麒麟V11 | 单进程 Streamlit + Python | ❌ 不需要 |
| B/S 架构 | 浏览器访问 | Streamlit 已实现 | ✅ 已满足 |
| 性能要求 | 无高并发要求 | 单用户运维场景 | ❌ 不需要 |
| 组件间通信 | 无分布式要求 | 函数调用即可 | ❌ 不需要 |
| 赛题关注点 | 安全护栏 > MCP > OS感知 | 单体分层已清晰 | ❌ 不需要 |

**但建议采用「逻辑微服务化」重构**（模块拆分更清晰，但仍在同一进程）：

```
当前（部分冗余）                          建议（逻辑微服务化）
─────────────────────────────         ─────────────────────────────
safety_gate/gate.py (两套模型)    →   safety_gate/gate.py (统一 GateResult)
audit/log.py (两套 API)           →   audit/log.py (统一 AuditLogger 类)
terminal/executor.py (两套函数)   →   terminal/executor.py (统一 Executor 类)
tools/registry.py (两套注册表)    →   tools/registry.py (统一 ToolRegistry 类)
```

**核心原则：去冗余、统一接口，而不是拆成独立进程。**

---

## 二、核心痛点解决方案（按 P0 → P1 顺序）

---

### P0-1: 最小权限代理执行 🔴 一票否决

**当前问题：**
```python
# terminal/executor.py 当前实现
proc = subprocess.run(command, shell=True, ...)  # ← 以当前用户身份执行
# sudo 参数仅做规则判定，不改变实际执行身份
```

**解决方案：在 `terminal/executor.py` 中实现三层权限执行模型**

```python
# 新增 security_agent/terminal/sandbox.py — 权限代理执行器

import os
import pwd
import subprocess
import grp

class PermissionLevel(Enum):
    READONLY = "readonly"       # 以 nobody/nogroup 执行（最低权限）
    RESTRICTED = "restricted"   # 以 security-agent-op 执行（受限运维账号）
    PRIVILEGED = "privileged"   # 以当前用户执行（需人工确认）
    ROOT = "root"               # sudo 执行（需多重审批）

class SandboxExecutor:
    """按风险等级降权执行命令"""
    
    # 受限运维账号（安装时自动创建）
    RESTRICTED_USER = "security-agent-op"
    RESTRICTED_GROUP = "security-agent-op"
    
    def execute(self, command: str, level: PermissionLevel) -> TerminalResult:
        if level == PermissionLevel.READONLY:
            # 以 nobody 执行纯读取命令
            return self._run_as_user(command, uid=65534, gid=65534)
        elif level == PermissionLevel.RESTRICTED:
            # 以受限运维账号执行
            return self._run_as_user(command, 
                uid=self._get_uid(self.RESTRICTED_USER),
                gid=self._get_gid(self.RESTRICTED_GROUP))
        elif level == PermissionLevel.PRIVILEGED:
            # 以当前用户执行（需 CONFIRM）
            return self._run_current_user(command)
        elif level == PermissionLevel.ROOT:
            # sudo 执行（需 ESCALATE 审批）
            return self._run_sudo(command)
    
    def _run_as_user(self, command, uid, gid):
        """核心：以指定 uid/gid 降权执行"""
        def demote():
            os.setgid(gid)
            os.setuid(uid)
        
        return subprocess.run(
            command, shell=True,
            preexec_fn=demote,  # ← 在执行前降权
            capture_output=True, text=True, timeout=30
        )
```

**配套措施：**
1. 安装脚本中自动创建受限账号：
```bash
# scripts/setup_restricted_user.sh
useradd -r -s /bin/false -M security-agent-op
usermod -aG systemd-journal security-agent-op  # 可读日志
```

2. 修改 `SafetyGate.evaluate_terminal()` 返回推荐权限级别：
```python
# gate.py 新增
if risk.level == RiskLevel.READONLY:
    recommended_permission = PermissionLevel.READONLY
elif risk.level == RiskLevel.REVERSIBLE:
    recommended_permission = PermissionLevel.RESTRICTED
elif risk.level == RiskLevel.IRREVERSIBLE:
    recommended_permission = PermissionLevel.PRIVILEGED
elif risk.level == RiskLevel.CRITICAL:
    recommended_permission = PermissionLevel.ROOT
```

**文件变更清单：**
| 操作 | 文件 | 内容 |
|------|------|------|
| 新建 | `security_agent/terminal/sandbox.py` | PermissionLevel + SandboxExecutor |
| 改造 | `security_agent/terminal/executor.py` | 替换 subprocess.run → SandboxExecutor |
| 改造 | `security_agent/safety_gate/gate.py` | GateResult 增加 recommended_permission |
| 新建 | `scripts/setup_restricted_user.sh` | 自动创建受限账号 |
| 改造 | `boot_start.sh` | 启动前检查受限账号是否存在 |

---

### P0-2: 全链路 Trace 贯穿 🔴 一票否决

**当前问题：**
- `gate.py` 自己生成 `trace_id` → 只覆盖 SafetyGate 阶段
- `audit/log.py` 自己生成 `event_id` → 互不关联
- Brain 推理过程、Orchestrator 编排过程 → 无日志

**解决方案：全局 TraceContext + 五阶段日志**

```python
# 新建 security_agent/audit/trace.py — 全局链路追踪

import contextvars
import uuid
import time
from dataclasses import dataclass, field

# 全局 trace context（contextvars 确保线程/协程安全）
_trace_ctx: contextvars.ContextVar = contextvars.ContextVar("trace_ctx")

@dataclass
class TraceSpan:
    span_id: str
    phase: str          # receive | perceive | plan | verify | execute
    started_at: float
    ended_at: float = 0.0
    input: str = ""
    output: str = ""
    metadata: dict = field(default_factory=dict)

class TraceContext:
    """五阶段全链路追踪"""
    
    def __init__(self, user_message: str = ""):
        self.trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        self.spans: list[TraceSpan] = []
        self.user_message = user_message
    
    # 在 orchestrator.py 中调用:
    # with trace.span("receive", user_message):
    #     ... 接收用户指令
    #
    # with trace.span("perceive", os_summary):
    #     ... 环境感知（自动采集 OS 状态）
    #
    # with trace.span("plan", plan_text):
    #     ... Brain 推理决策
    #
    # with trace.span("verify", verdict):
    #     ... SafetyGate 安全校验
    #
    # with trace.span("execute", result):
    #     ... 终端执行结果
    #
    # trace.flush() → 写入 audit.log（一条包含所有 span 的完整记录）

# 使用方式（在 orchestrator.py 中改造）:
# trace = TraceContext(user_message)
# trace.span("receive", data=user_message)
# trace.span("perceive", data=os_context)
# trace.span("plan", data=brain_output)
# trace.span("verify", data=gate_result.to_dict())
# trace.span("execute", data=terminal_result.to_dict())
# trace.flush()
```

**文件变更清单：**
| 操作 | 文件 | 内容 |
|------|------|------|
| 新建 | `security_agent/audit/trace.py` | TraceContext + TraceSpan |
| 改造 | `security_agent/agent/orchestrator.py` | 引入 TraceContext，五个 with 块 |
| 改造 | `security_agent/agent/brain.py` | Brain 推理过程记录到 span |
| 改造 | `security_agent/safety_gate/gate.py` | GateResult 使用外部传入的 trace_id |
| 改造 | `security_agent/audit/log.py` | 统一为 AuditLogger 类，支持 trace 写入 |

---

### P0-3: 代码去冗余（两套实现统一）

**当前冗余清单与统一方案：**

| 模块 | 旧实现 | 新实现 | 统一后保留 |
|------|--------|--------|----------|
| safety_gate | `SafetyVerdict` (旧) | `GateResult` (新) | **GateResult** |
| safety_gate | `SafetyGate.evaluate()` | `SafetyGate.evaluate_terminal()` | **evaluate_terminal + evaluate_tool** |
| intent | `analyze_user_intent()` | `IntentAuditor.audit()` | **IntentAuditor.audit()** |
| audit | `append_audit()` | `AuditLogger.log()` | **AuditLogger.log()** |
| terminal | `run_terminal_sync()` | `run_terminal()` | **统一为 Executor.execute()** |
| tools | `TOOL_REGISTRY` (dict) | `ToolRegistry` (class) | **ToolRegistry** (class) |

**执行策略：保留新接口，删除旧接口，全局替换引用。**

---

### P1-1: MCP 插件热插拔

**当前问题：** `TOOL_REGISTRY` 是静态字典，新增工具需改代码。

**解决方案：PluginManager + 文件系统扫描**

```python
# 改造 security_agent/tools/registry.py

class PluginManager:
    """从 plugins/ 目录自动发现并加载 MCP Tools"""
    
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self._loaded: dict[str, Any] = {}
    
    def discover(self) -> list[str]:
        """扫描 plugins/ 下所有 .py 文件"""
        plugins = []
        for f in self.plugin_dir.glob("*.py"):
            if f.name.startswith("_"): continue
            plugins.append(f.stem)
        return plugins
    
    def load(self, name: str):
        """动态加载插件模块"""
        spec = importlib.util.spec_from_file_location(
            name, self.plugin_dir / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # 插件模块需导出 register(mcp_server) 函数
        module.register(self.mcp_server)
        self._loaded[name] = module
    
    def unload(self, name: str):
        """卸载插件"""
        if name in self._loaded:
            # 从 MCP Server 注销该插件的所有 tools
            # del sys.modules[...]
            del self._loaded[name]
```

---

### P1-2: OS 主动感知层 (EnvironmentProbe)

**当前问题：** LLM 需手动决定调用 tool 获取系统状态，赛题要求"自动调用"。

**解决方案：在每次请求前自动注入系统状态摘要**

```python
# 新建 security_agent/agent/perception.py

class EnvironmentProbe:
    """请求前自动采集 OS 状态摘要，注入 Brain 上下文"""
    
    def probe(self) -> str:
        """采集并格式化为 LLM 可读的上下文"""
        return f"""
## 当前系统状态（自动采集 {datetime.now()}）

### 资源使用
- CPU: {self._cpu_percent()}%
- 内存: {self._mem_info()}
- 磁盘: {self._disk_usage()}

### 关键进程 (Top 5 by CPU)
{self._top_processes()}

### 网络监听端口
{self._listening_ports()}

### 最近异常日志 (journalctl -p err, 最近5条)
{self._recent_errors()}
"""
```

**在 orchestrator.py 中集成：**
```python
def handle_request(self, user_message: str):
    trace = TraceContext(user_message)
    
    with trace.span("receive", user_message):
        pass
    
    with trace.span("perceive"):
        probe = EnvironmentProbe()
        os_context = probe.probe()  # ← 自动采集
    
    with trace.span("plan"):
        # os_context 注入到 Brain 的 system prompt
        response = self.brain.chat(user_message, extra_context=os_context)
    ...
```

---

### P1-3: 文件语义识别（"清理系统垃圾"场景）

**当前问题：** RiskAssessor 只能判定 `rm` 命令的风险等级，不能判断文件是否可删除。

**解决方案：文件重要性评估规则库**

```python
# 新建 security_agent/safety_gate/file_rules.py

FILE_IMPORTANCE_RULES = {
    # 不可删除（系统关键）
    "critical": [
        "/etc/passwd", "/etc/shadow", "/etc/sudoers",
        "/etc/fstab", "/boot/*", "/lib/**/*.so*",
        "/var/lib/mysql/**/ibdata*",   # 数据库核心文件
        "/var/lib/postgresql/**/base/*",
        "/etc/kysec/**",               # 麒麟安全策略
    ],
    # 需确认（运维相关）
    "important": [
        "/var/log/**/*.log",           # 日志文件（可能有价值）
        "/etc/**/*.conf",              # 配置文件
        "/home/*/.*",                  # 用户隐藏配置
    ],
    # 可清理（安全）
    "cleanable": [
        "/tmp/**", "/var/tmp/**",
        "/var/cache/**", "/var/log/**/*.gz",  # 已轮转的旧日志
        "~/.cache/**", "~/.local/share/Trash/**",
    ]
}

class FileImportanceAnalyzer:
    """判断文件重要性"""
    
    def classify(self, path: str) -> str:
        """返回: critical | important | cleanable | unknown"""
        # 基于 glob 匹配和麒麟路径适配
    
    def can_delete(self, path: str, user_intent: str) -> tuple[bool, str]:
        """
        综合判断：用户意图 + 文件重要性 + 当前权限
        """
        level = self.classify(path)
        if level == "critical":
            return False, f"关键系统文件禁止删除: {path}"
        if level == "cleanable":
            return True, "可安全清理"
        if level == "important" and "清理垃圾" in user_intent:
            return False, f"日志文件需确认后删除: {path}"
```

---

## 三、实施优先级与工作量

```
第一周（P0 必做）：
  Day 1-2: P0-3 代码去冗余（6个模块统一接口）            ≈ 4h
  Day 2-3: P0-1 权限隔离（SandboxExecutor + 受限账号）   ≈ 6h
  Day 3-4: P0-2 全链路 Trace（TraceContext + 5阶段日志） ≈ 5h
  Day 5:   集成测试 + 回归                                ≈ 3h

第二周（P1 核心功能）：
  Day 1-2: P1-2 OS主动感知层 (EnvironmentProbe)          ≈ 4h
  Day 2-3: P1-1 MCP热插拔 (PluginManager)                ≈ 4h
  Day 3-4: P1-3 文件语义识别 (FileImportanceAnalyzer)   ≈ 3h
  Day 4-5: UI确认流程串联 (CONFIRM弹窗)                   ≈ 3h
  Day 5:   安全测试用例                                   ≈ 2h

第三周（P2 加分 + 部署验证）：
  Day 1-2: 麒麟 LooongArch 环境部署验证
  Day 3-4: 演示视频录制 + 文档完善
  Day 5:   P2 加分项（KYSEC联动、对抗样本检测等）
```

---

## 四、关键提醒

1. **不要过度工程化** — 竞品评审看的是安全能力完整性，不是架构复杂度。微服务对于单机部署的运维Agent是无意义的开销。
2. **安全护栏是评审第一关注点** — 务必让 SafetyGate → SandboxExecutor → TraceContext 链路完整无误。
3. **"清理系统垃圾"场景必须能跑通** — 这是评审最可能现场演示的场景。
4. **麒麟特色加分** — 在 OS 感知层适配 `kylin-log` / `kysec` / `kylin-security` 命令，展示国产化深度。
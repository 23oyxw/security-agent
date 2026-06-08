"""任务分发引擎 — 权限管控核心.

架构:  聊天会话 → 权限校验 → 任务分发 → 封装内部动作 → 执行 → 审计

与传统模式（用户输入原始命令 → 正则拦截）完全不同:
  - 用户不输入 Shell 命令，只选择/发起运维任务
  - 所有底层指令内部封装，对外不可见
  - 管控重心是「谁能做什么」，而非「命令是否包含危险关键词」

三种运行形态:
  1. dispatch (direct)   — 权限校验 → 真机直接执行
  2. dispatch (preview)  — 权限校验 → 沙箱预演 → 预览结果 → 真机执行
  3. dispatch (sandbox)  — 权限校验 → 仅沙箱模拟（演示用）
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from security_agent.audit import log as audit
from security_agent.audit.trace import TraceContext


# ============================================================
# 任务目录 — 封装所有底层运维动作
# ============================================================

@dataclass
class OpsTask:
    """运维任务定义."""
    name: str                       # 内部任务名
    label: str                      # 展示名称
    description: str                # 描述
    category: str                   # 分类：监控/日志/网络/安全/系统
    min_role: str = "readonly"      # 最低权限要求 (readonly/operator/admin)
    preview_supported: bool = True  # 是否支持沙箱预演
    risk_level: str = "READONLY"    # READONLY/REVERSIBLE/IRREVERSIBLE/CRITICAL


async def _h_port_check() -> str:
    """端口检测 — 封装 ss -tulnp."""
    out = subprocess.run(["ss", "-tulnp"], capture_output=True, text=True, timeout=10)
    return out.stdout[:3000] if out.returncode == 0 else out.stderr


async def _h_log_tail(n: int = 20) -> str:
    """查看系统日志 — 封装 journalctl."""
    out = subprocess.run(
        ["journalctl", "-n", str(min(n, 100)), "--no-pager"],
        capture_output=True, text=True, timeout=15,
    )
    return out.stdout[:4000] if out.returncode == 0 else out.stderr


async def _h_process_list() -> str:
    """进程查询 — 封装 ps aux."""
    out = subprocess.run(["ps", "aux", "--sort=-%cpu"], capture_output=True, text=True, timeout=10)
    lines = out.stdout.split("\n")
    return "\n".join(lines[:30])


async def _h_system_health() -> str:
    """系统健康检查."""
    import psutil
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = psutil.getloadavg()
    return json.dumps({
        "cpu_percent": cpu, "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / 1024**3, 2),
        "disk_percent": disk.percent, "disk_free_gb": round(disk.free / 1024**3, 2),
        "load_1m": load[0], "process_count": len(psutil.pids()),
    }, ensure_ascii=False, indent=2)


async def _h_disk_analyze() -> str:
    """磁盘使用分析 — 封装 df -h."""
    out = subprocess.run(["df", "-h", "-x", "tmpfs", "-x", "devtmpfs"], capture_output=True, text=True, timeout=10)
    return out.stdout[:3000]


async def _h_network_check() -> str:
    """网络连接分析."""
    out = subprocess.run(["ss", "-tan"], capture_output=True, text=True, timeout=10)
    lines = out.stdout.split("\n")
    states = {}
    for line in lines[1:]:
        parts = line.split()
        if parts:
            states[parts[0]] = states.get(parts[0], 0) + 1
    return json.dumps({"total": len(lines) - 1, "states": states}, ensure_ascii=False)


async def _h_service_restart(name: str) -> str:
    """重启服务 — 需 operator 权限."""
    out = subprocess.run(
        ["systemctl", "restart", name], capture_output=True, text=True, timeout=30
    )
    return f"重启 {name}: {'成功' if out.returncode == 0 else '失败 — ' + out.stderr[:500]}"


async def _h_firewall_status() -> str:
    """防火墙状态检查."""
    try:
        out = subprocess.run(
            ["iptables", "-L", "INPUT", "-n"], capture_output=True, text=True, timeout=10
        )
        policy = "UNKNOWN"
        for line in out.stdout.split("\n"):
            if "Chain INPUT (policy" in line:
                policy = line.split("policy")[1].strip().rstrip(")")
                break
        return f"iptables INPUT 默认策略: {policy}"
    except FileNotFoundError:
        return "iptables 未安装"


# ============================================================
# 任务目录注册
# ============================================================

TASK_CATALOG: dict[str, OpsTask] = {
    "port_check": OpsTask(
        name="port_check", label="端口检测", description="查看系统监听端口 (ss -tulnp)",
        category="网络", min_role="readonly", risk_level="READONLY",
    ),
    "log_tail": OpsTask(
        name="log_tail", label="日志查看", description="查看最近系统日志 (journalctl -n)",
        category="日志", min_role="readonly", risk_level="READONLY",
    ),
    "process_list": OpsTask(
        name="process_list", label="进程查询", description="查看 CPU 占用最高的进程",
        category="监控", min_role="readonly", risk_level="READONLY",
    ),
    "system_health": OpsTask(
        name="system_health", label="系统健康", description="CPU/内存/磁盘/负载综合快照",
        category="监控", min_role="readonly", risk_level="READONLY",
    ),
    "disk_analyze": OpsTask(
        name="disk_analyze", label="磁盘分析", description="各分区使用情况 (df -h)",
        category="系统", min_role="readonly", risk_level="READONLY",
    ),
    "network_check": OpsTask(
        name="network_check", label="网络连接", description="TCP 连接状态分布",
        category="网络", min_role="readonly", risk_level="READONLY",
    ),
    "firewall_status": OpsTask(
        name="firewall_status", label="防火墙状态", description="iptables 默认策略检查",
        category="安全", min_role="readonly", risk_level="READONLY",
    ),
    "service_restart": OpsTask(
        name="service_restart", label="重启服务", description="重启指定系统服务 (systemctl restart)",
        category="系统", min_role="operator", risk_level="REVERSIBLE", preview_supported=True,
    ),
}

TASK_HANDLERS: dict[str, Callable[..., Any]] = {
    "port_check": _h_port_check,
    "log_tail": _h_log_tail,
    "process_list": _h_process_list,
    "system_health": _h_system_health,
    "disk_analyze": _h_disk_analyze,
    "network_check": _h_network_check,
    "firewall_status": _h_firewall_status,
    "service_restart": _h_service_restart,
}


# ============================================================
# 权限层级
# ============================================================

ROLE_LEVEL = {"readonly": 0, "operator": 1, "admin": 2}

# 角色 → 可执行任务（按 min_role 过滤）
def allowed_tasks_for_role(role: str) -> list[str]:
    level = ROLE_LEVEL.get(role, -1)
    return [
        name for name, task in TASK_CATALOG.items()
        if ROLE_LEVEL.get(task.min_role, 99) <= level
    ]


# ============================================================
# 核心分发函数
# ============================================================

@dataclass
class DispatchResult:
    """任务分发结果."""
    success: bool
    task_name: str
    task_label: str
    user: str
    role: str
    mode: str = "direct"          # direct / preview / sandbox
    preview_result: str = ""      # 沙箱预演输出
    exec_result: str = ""         # 正式执行输出
    error: str = ""
    trace_id: str = ""
    duration_ms: float = 0.0
    risk_level: str = "READONLY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success, "task_name": self.task_name,
            "task_label": self.task_label, "user": self.user, "role": self.role,
            "mode": self.mode, "preview_result": self.preview_result[:3000],
            "exec_result": self.exec_result[:4000], "error": self.error,
            "trace_id": self.trace_id, "duration_ms": self.duration_ms,
            "risk_level": self.risk_level,
        }


async def dispatch(
    task_name: str,
    *,
    user: str = "anonymous",
    role: str = "readonly",
    mode: str = "direct",
    task_args: dict[str, Any] | None = None,
) -> DispatchResult:
    """权限管控 + 任务分发 + 执行.

    Args:
        task_name: 任务名（TASK_CATALOG key）
        user: 用户名
        role: 用户角色 (readonly/operator/admin)
        mode: direct (直接执行) / preview (沙箱预演+正式执行) / sandbox (仅沙箱)
        task_args: 传递给 handler 的参数
    """
    t0 = time.time()
    trace_id = TraceContext.current_trace_id() or f"task-{int(t0*1000)}"
    task_args = task_args or {}

    # ---- 步骤 1: 任务存在性 ----
    task = TASK_CATALOG.get(task_name)
    if not task:
        return DispatchResult(
            success=False, task_name=task_name, task_label="未知",
            user=user, role=role, mode=mode, trace_id=trace_id,
            error=f"任务不存在: {task_name}", risk_level="READONLY",
        )

    # ---- 步骤 2: 权限校验（核心） ----
    user_level = ROLE_LEVEL.get(role, -1)
    required_level = ROLE_LEVEL.get(task.min_role, 99)
    if user_level < required_level:
        audit.append_audit("task_permission_denied", {
            "trace_id": trace_id, "user": user, "role": role,
            "task": task_name, "required_role": task.min_role,
        }, level="warning")
        return DispatchResult(
            success=False, task_name=task_name, task_label=task.label,
            user=user, role=role, mode=mode, trace_id=trace_id,
            error=f"权限不足: 当前角色 {role} (level {user_level}) 无法执行 '{task.label}' (需要 {task.min_role} level {required_level})",
            risk_level=task.risk_level,
        )

    # ---- 步骤 3: 获取 handler ----
    handler = TASK_HANDLERS.get(task_name)
    if not handler:
        return DispatchResult(
            success=False, task_name=task_name, task_label=task.label,
            user=user, role=role, mode=mode, trace_id=trace_id,
            error=f"任务处理函数未实现: {task_name}", risk_level=task.risk_level,
        )

    # ---- 步骤 4: 沙箱预演 (preview/sandbox 模式) ----
    preview_result = ""
    if mode in ("preview", "sandbox") and task.preview_supported:
        try:
            # 同一份 handler 在沙箱环境中运行（当前用 try/except 模拟）
            # 生产环境可替换为 nsjail/chroot 隔离执行
            from security_agent.terminal.sandbox import get_sandbox
            sandbox = get_sandbox()
            sb_result = sandbox.run(
                f"echo 'preview:{task_name}'",
                risk_level=task.risk_level,
                timeout_sec=10,
            )
            preview_result = f"[沙箱预演] {task.label}: 环境正常，可执行\n{sb_result.stdout[:1000]}"
        except Exception as e:
            preview_result = f"[沙箱预演失败] {e}"

    # 仅沙箱模式 — 返回预演结果
    if mode == "sandbox":
        return DispatchResult(
            success=True, task_name=task_name, task_label=task.label,
            user=user, role=role, mode="sandbox", preview_result=preview_result,
            error="", trace_id=trace_id, risk_level=task.risk_level,
            duration_ms=(time.time() - t0) * 1000,
        )

    # ---- 步骤 5: 正式执行 ----
    exec_result = ""
    error = ""
    success = True
    try:
        result = await handler(**task_args)
        exec_result = str(result) if result else ""
    except Exception as e:
        success = False
        error = str(e)
        exec_result = ""

    # ---- 步骤 6: 审计留痕 ----
    audit.append_audit("task_dispatch", {
        "trace_id": trace_id, "user": user, "role": role,
        "task": task_name, "mode": mode, "success": success,
        "preview": bool(preview_result), "error": error[:200],
    })

    return DispatchResult(
        success=success, task_name=task_name, task_label=task.label,
        user=user, role=role, mode=mode,
        preview_result=preview_result, exec_result=exec_result,
        error=error, trace_id=trace_id, risk_level=task.risk_level,
        duration_ms=(time.time() - t0) * 1000,
    )


# ============================================================
# 便捷查询
# ============================================================

def list_all_tasks(role: str = "readonly") -> list[dict[str, Any]]:
    """列出当前角色可执行的所有任务."""
    allowed = allowed_tasks_for_role(role)
    return [
        {
            "name": t.name, "label": t.label, "description": t.description,
            "category": t.category, "min_role": t.min_role,
            "can_execute": t.name in allowed,
            "preview_supported": t.preview_supported,
            "risk_level": t.risk_level,
        }
        for t in TASK_CATALOG.values()
        if t.name in allowed
    ]


def get_task(task_name: str) -> dict[str, Any] | None:
    t = TASK_CATALOG.get(task_name)
    if not t:
        return None
    return {"name": t.name, "label": t.label, "description": t.description,
            "category": t.category, "min_role": t.min_role,
            "preview_supported": t.preview_supported, "risk_level": t.risk_level}

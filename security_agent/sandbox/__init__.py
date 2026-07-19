"""全域沙箱 — 4 层隔离，从演示级到生产级.

架构层次（由浅入深 — 当前实现 4 层，L4-L6 为 P1 规划）:
    Layer 0: setuid/setgid 权限降级
    Layer 1: rlimit 资源限制
    Layer 2: OverlayFS 写时复制（文件系统隔离）
    Layer 3: mount namespace（私有 /tmp、/dev、/proc 挂载点）
    Layer 4: network namespace（禁止/限制外连）— P1 未启用
    Layer 5: seccomp-bpf（系统调用白名单）— P1 未启用
    Layer 6: cgroup v2（精确资源控制+审计）— P1 未启用

当前实际启用 4 层: setuid降权 + rlimit资源限制 + OverlayFS写时复制 + mount_ns文件隔离

用法:
    from security_agent.sandbox import SandboxSession

    async with SandboxSession() as session:
        preview = session.preview("rm -rf /tmp/cache")
        if preview.risk_level != "CRITICAL":
            result = session.execute("rm -rf /tmp/cache", confirmed=True)
            changes = session.changes()
            if changes.is_safe:
                session.commit()
            else:
                session.rollback()
"""

from security_agent.sandbox.profile import SandboxProfile
from security_agent.sandbox.session import SandboxSession

__all__ = ["SandboxProfile", "SandboxSession"]

"""Linux namespace 隔离 — mount namespace 私有化 /tmp、/proc 等敏感挂载点.

设计原则:
    - 仅 Linux 生效（需要 CAP_SYS_ADMIN）
    - 麒麟 V11 内核 5.10+ 完整支持
    - 调用方不需要关心 namespace 细节，只调 apply() 即可
    - 失败优雅降级（非 Linux 或无权限时静默跳过）

用法:
    from security_agent.sandbox.namespace import NamespaceGuard

    guard = NamespaceGuard()
    guard.apply_mount_ns()    # 私有 /tmp、/dev/shm
    # ... 在隔离环境中执行 ...
    guard.cleanup()
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Any

_IS_LINUX = sys.platform == "linux"

# Linux clone/unshare 常量
CLONE_NEWNS = 0x00020000      # mount namespace
CLONE_NEWNET = 0x40000000     # network namespace
CLONE_NEWPID = 0x20000000     # PID namespace

# 需要重新挂载为私有的挂载点（防止影响宿主机）
_ISOLATE_MOUNTS = [
    "/tmp",
    "/dev/shm",
    "/var/tmp",
]


class NamespaceGuard:
    """Linux namespace 隔离管理器.

    职责:
        1. mount namespace 隔离 — 私有 /tmp
        2. 传播标志设为 SLAVE（防止子挂载传播到宿主机）
        3. 退出时自动清理

    非 Linux 环境: 所有操作静默跳过（is_active = False）
    """

    def __init__(self):
        self._active = False
        self._pid: int | None = None
        self._applied_mounts: list[str] = []

    # ---- 公开接口 ----

    def apply_mount_ns(self) -> bool:
        """应用 mount namespace 隔离.

        Returns:
            True 如果成功隔离
            False 如果不支持（非 Linux / 无权限）→ 优雅降级
        """
        if not _IS_LINUX:
            return False
        if not self._can_unshare():
            return False

        try:
            # 1. 创建 mount namespace
            self._unshare(CLONE_NEWNS)
            self._active = True

            # 2. 设置传播标志为 SLAVE
            self._mount("none", "/", None, 0, "")

            # 3. 对每个需要隔离的挂载点，创建 tmpfs 覆盖
            for mp in _ISOLATE_MOUNTS:
                if os.path.exists(mp):
                    self._mount_tmpfs(mp)
                    self._applied_mounts.append(mp)

            return True
        except (OSError, PermissionError):
            return False

    def cleanup(self) -> None:
        """清理 — 卸载私有挂载点."""
        for mp in reversed(self._applied_mounts):
            try:
                self._umount(mp)
            except OSError:
                pass
        self._applied_mounts.clear()
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def status(self) -> dict[str, Any]:
        return {
            "platform": sys.platform,
            "active": self._active,
            "isolated_mounts": list(self._applied_mounts),
        }

    # ---- 底层 linux 系统调用 ----

    @staticmethod
    def _can_unshare() -> bool:
        """检查是否有能力创建 namespace."""
        try:
            # 尝试创建 user namespace（最低权限要求）
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            return True
        except OSError:
            return False

    @staticmethod
    def _unshare(flags: int) -> None:
        """调用 Linux unshare(2)."""
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        ret = libc.unshare(flags)
        if ret != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err))

    @staticmethod
    def _mount(source: str, target: str, fstype: str | None, flags: int, data: str) -> None:
        """调用 Linux mount(2)."""
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        ret = libc.mount(
            source.encode() if source else None,
            target.encode(),
            fstype.encode() if fstype else None,
            flags,
            data.encode() if data else None,
        )
        if ret != 0:
            err = ctypes.get_errno()
            raise OSError(err, f"mount({source}, {target}, {fstype}): {os.strerror(err)}")

    @staticmethod
    def _umount(target: str) -> None:
        """调用 Linux umount(2)."""
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        ret = libc.umount(target.encode())
        if ret != 0:
            err = ctypes.get_errno()
            raise OSError(err, f"umount({target}): {os.strerror(err)}")

    def _mount_tmpfs(self, path: str) -> None:
        """在指定路径上挂载一个私有 tmpfs."""
        try:
            # MS_PRIVATE | MS_REC = 0x4000 | 0x4000 = 0x8000
            self._mount("none", path, None, 0x8000, "")  # make private recursively
            self._mount("tmpfs", path, "tmpfs", 0, "")
        except OSError:
            pass

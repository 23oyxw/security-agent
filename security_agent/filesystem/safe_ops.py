"""SafeFileOps — 安全文件操作，所有写操作经过沙箱保护.

设计原则（可追溯 + 自愈优先）:
    任何文件写入都:
    1. 自动创建版本（通过 FileVersionManager）
    2. 可选 OverlayFS 保护（通过 SandboxSession）
    3. 记录审计日志

用法:
    from security_agent.filesystem import SafeFileOps

    ops = SafeFileOps()
    ops.write("/etc/config.conf", new_content, message="update nginx config")
    ops.read("/etc/config.conf")
    ops.history("/etc/config.conf")  # 查看变更历史
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class SafeFileOps:
    """安全文件操作 — 版本化 + 审计."""

    def __init__(self, version_dir: str = "data/versions"):
        from security_agent.filesystem.version_manager import FileVersionManager
        self._versions = FileVersionManager(version_dir)

    # ---- 读 ----

    def read(self, path: str | Path, version_id: str | None = None) -> bytes | None:
        """读取文件（默认最新版本）."""
        return self._versions.read(path, version_id)

    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str | None:
        """读取文本文件."""
        content = self.read(path)
        if content is None:
            return None
        return content.decode(encoding)

    # ---- 写 ----

    def write(
        self,
        path: str | Path,
        content: str | bytes,
        *,
        message: str = "",
        trace_id: str = "",
    ) -> dict[str, Any]:
        """安全写入文件（自动版本化）."""
        version = self._versions.write(
            path, content,
            created_by="safe_ops",
            trace_id=trace_id,
            message=message,
        )
        return {
            "ok": True,
            "path": str(path),
            "version_id": version.version_id,
            "operation": version.operation,
            "size_bytes": version.size_bytes,
            "hash": version.content_hash[:16],
        }

    def append(
        self,
        path: str | Path,
        content: str,
        *,
        message: str = "",
    ) -> dict[str, Any]:
        """追加内容到文件末尾."""
        fp = Path(path)
        existing = ""
        if fp.exists():
            try:
                existing = fp.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                existing = ""
        return self.write(path, existing + "\n" + content, message=message)

    # ---- 历史 ----

    def history(self, path: str | Path) -> list[dict[str, Any]]:
        """获取文件的版本历史."""
        versions = self._versions.history(path, limit=30)
        return [v.to_dict() for v in versions]

    def rollback(self, path: str | Path, version_id: str) -> dict[str, Any]:
        """回滚到指定版本."""
        version = self._versions.rollback(path, version_id)
        if version is None:
            return {"ok": False, "error": f"Version {version_id} not found"}
        return {"ok": True, "path": str(path), "rolled_back_to": version_id}

    # ---- 删除 ----

    def delete(self, path: str | Path) -> dict[str, Any]:
        """安全删除文件（记录版本后删除）."""
        version = self._versions.delete(path)
        return {"ok": True, "path": str(path), "version_id": version.version_id}

    # ---- 批量 ----

    def write_batch(
        self,
        files: dict[str, str | bytes],
        *,
        message: str = "",
    ) -> list[dict[str, Any]]:
        """批量安全写入."""
        results = []
        for path, content in files.items():
            results.append(self.write(path, content, message=message))
        return results

    # ---- 统计 ----

    def stats(self) -> dict[str, Any]:
        return self._versions.stats()

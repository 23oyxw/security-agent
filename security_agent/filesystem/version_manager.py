"""FileVersionManager — 文件版本化管理，每次写操作自动创建版本.

设计原则（可追溯）:
    每次文件变更自动保存增量 diff，支持:
    - 版本回滚到任意历史版本
    - 变更审计（谁在何时改了什么）
    - 基于内容的去重（内容未变不创建新版本）

用法:
    from security_agent.filesystem import FileVersionManager

    mgr = FileVersionManager(storage_dir="data/versions")
    v = mgr.write(Path("/etc/config.conf"), new_content)
    history = mgr.history(Path("/etc/config.conf"))
    mgr.rollback(Path("/etc/config.conf"), version_id)
"""

from __future__ import annotations

import difflib
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileVersion:
    """一个文件版本."""
    version_id: str
    file_path: str
    parent_version: str | None      # 前一版本 ID
    content_hash: str               # sha256
    size_bytes: int
    diff_type: str                  # "full" | "incremental"
    diff: str                       # unified diff 文本
    operation: str                  # "create" | "modify" | "delete"
    created_by: str = ""
    created_at: str = ""
    trace_id: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "file_path": self.file_path,
            "parent_version": self.parent_version,
            "content_hash": self.content_hash,  # 完整 sha256 hex (64 chars)
            "size_bytes": self.size_bytes,
            "diff_type": self.diff_type,
            "operation": self.operation,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "trace_id": self.trace_id,
            "message": self.message,
            "diff_preview": self.diff[:500] if self.diff else "",
        }


class FileVersionManager:
    """文件版本管理器.

    存储结构:
        {storage_dir}/
            versions.jsonl    # 版本元数据（append-only）
            blobs/{hash}      # 内容 blob（去重存储）
    """

    def __init__(self, storage_dir: str | Path = "data/versions"):
        self._dir = Path(storage_dir)
        self._blobs_dir = self._dir / "blobs"
        self._index_path = self._dir / "versions.jsonl"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._blobs_dir.mkdir(parents=True, exist_ok=True)

    # ---- 核心操作 ----

    def write(
        self,
        file_path: str | Path,
        content: str | bytes,
        *,
        created_by: str = "",
        trace_id: str = "",
        message: str = "",
    ) -> FileVersion:
        """写入文件并自动创建版本.

        如果内容未变，不创建新版本（去重）。
        """
        fp = Path(file_path)
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        new_hash = hashlib.sha256(content_bytes).hexdigest()

        # 检查是否内容未变
        last = self._latest_version(fp)
        if last and last.content_hash == new_hash:
            return last

        # 获取旧内容用于 diff
        old_content = ""
        if fp.exists():
            try:
                old_content = fp.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                old_content = ""

        new_text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")

        # 生成 diff
        if old_content:
            diff_lines = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=str(fp),
                tofile=str(fp),
            ))
            diff_text = "".join(diff_lines)
            diff_type = "incremental"
            operation = "modify"
        else:
            diff_text = new_text[:2000]
            diff_type = "full"
            operation = "create"

        # 存储 blob
        blob_path = self._blobs_dir / new_hash[:2] / new_hash
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        if not blob_path.exists():
            blob_path.write_bytes(content_bytes)

        from security_agent.timeutil import now_iso

        version = FileVersion(
            version_id=uuid.uuid4().hex[:12],
            file_path=str(fp),
            parent_version=last.version_id if last else None,
            content_hash=new_hash,
            size_bytes=len(content_bytes),
            diff_type=diff_type,
            diff=diff_text,
            operation=operation,
            created_by=created_by or "agent",
            created_at=now_iso(),
            trace_id=trace_id,
            message=message,
        )

        # 写入实际文件
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(content_bytes)

        # 追加版本记录
        self._append_version(version)

        return version

    def read(self, file_path: str | Path, version_id: str | None = None) -> bytes | None:
        """读取文件内容（默认最新，可指定版本）."""
        fp = Path(file_path)

        if version_id:
            version = self._find_version(fp, version_id)
            if version is None:
                return None
            blob_path = self._blobs_dir / version.content_hash[:2] / version.content_hash
            if blob_path.exists():
                return blob_path.read_bytes()
            return None

        # 默认：读当前文件
        if fp.exists():
            return fp.read_bytes()
        return None

    def history(self, file_path: str | Path, limit: int = 50) -> list[FileVersion]:
        """获取文件的历史版本列表（最新在前）."""
        fp = str(file_path)
        versions = []
        if self._index_path.exists():
            for line in self._index_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("file_path") == fp:
                        versions.append(FileVersion(
                            version_id=data["version_id"],
                            file_path=data["file_path"],
                            parent_version=data.get("parent_version"),
                            content_hash=data["content_hash"],
                            size_bytes=data["size_bytes"],
                            diff_type=data.get("diff_type", "incremental"),
                            diff=data.get("diff", ""),
                            operation=data.get("operation", "modify"),
                            created_by=data.get("created_by", ""),
                            created_at=data.get("created_at", ""),
                            trace_id=data.get("trace_id", ""),
                            message=data.get("message", ""),
                        ))
                except (json.JSONDecodeError, KeyError):
                    continue
        return list(reversed(versions))[-limit:]

    def rollback(self, file_path: str | Path, version_id: str) -> FileVersion | None:
        """回滚到指定版本（本质上是写入该版本的内容）."""
        content = self.read(file_path, version_id)
        if content is None:
            return None
        return self.write(
            file_path,
            content,
            created_by="rollback",
            message=f"Rolled back to {version_id}",
        )

    def delete(self, file_path: str | Path, created_by: str = "") -> FileVersion:
        """标记文件为已删除（不创建物理删除，记录版本）."""
        from security_agent.timeutil import now_iso

        fp = Path(file_path)
        version = FileVersion(
            version_id=uuid.uuid4().hex[:12],
            file_path=str(fp),
            parent_version=None,
            content_hash="",
            size_bytes=0,
            diff_type="full",
            diff="",
            operation="delete",
            created_by=created_by or "agent",
            created_at=now_iso(),
        )
        self._append_version(version)
        return version

    # ---- 内部 ----

    def _latest_version(self, fp: Path) -> FileVersion | None:
        history = self.history(str(fp), limit=1)
        return history[0] if history else None

    def _find_version(self, fp: Path, version_id: str) -> FileVersion | None:
        for v in self.history(str(fp)):
            if v.version_id == version_id:
                return v
        return None

    def _append_version(self, version: FileVersion) -> None:
        record = version.to_dict()
        with open(self._index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def stats(self) -> dict[str, Any]:
        """版本库统计."""
        if not self._index_path.exists():
            return {"total_versions": 0, "tracked_files": 0}
        lines = self._index_path.read_text(encoding="utf-8").splitlines()
        files = set()
        for line in lines:
            if not line.strip():
                continue
            try:
                files.add(json.loads(line).get("file_path", ""))
            except json.JSONDecodeError:
                pass
        return {
            "total_versions": len([l for l in lines if l.strip()]),
            "tracked_files": len(files),
        }

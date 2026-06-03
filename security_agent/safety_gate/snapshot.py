"""快照管理器 — 自动备份/一键回滚（赛题核心得分点）.

在IRREVERSIBLE操作前自动创建快照，用户可随时回滚到操作前状态。
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class SnapshotRecord:
    """单个快照记录."""
    id: str
    created_at: str
    operation: str                                  # 触发快照的操作描述
    risk_level: str                                 # 风险等级
    user: str = ""                                  # 触发用户
    path: str = ""                                  # 快照存放路径
    files_before: list[str] = field(default_factory=list)  # 快照前文件状态
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        if not self.created_at:
            return 0.0
        try:
            dt = datetime.datetime.fromisoformat(self.created_at)
            return (datetime.datetime.now() - dt).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "operation": self.operation,
            "risk_level": self.risk_level,
            "user": self.user,
            "path": self.path,
            "files_before": self.files_before[:10],
            "files_count": len(self.files_before),
        }


class SnapshotManager:
    """快照管理器.

    在不可逆操作前自动备份关键文件/目录状态，支持一键回滚。

    用法:
        mgr = SnapshotManager(base_dir="/var/lib/security-agent/snapshots")
        snap = mgr.create_snapshot(
            operation="修改SSH配置",
            risk_level="IRREVERSIBLE",
            paths=["/etc/ssh/sshd_config", "/etc/ssh/sshd_config.d/"],
        )
        # ... 执行操作后如果出现问题 ...
        mgr.restore_snapshot(snap.id)
    """

    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            # 默认放在项目 data 目录下
            base_dir = Path(__file__).parent.parent.parent / "data" / "snapshots"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self.base_dir / "_index.json"
        self._index: dict[str, dict[str, Any]] = {}
        self._load_index()

    def _load_index(self) -> None:
        """加载快照索引."""
        if self._index_file.exists():
            try:
                self._index = json.loads(self._index_file.read_text())
            except (json.JSONDecodeError, OSError):
                self._index = {}

    def _save_index(self) -> None:
        """保存快照索引."""
        self._index_file.write_text(json.dumps(self._index, indent=2, ensure_ascii=False))

    def _get_file_state(self, paths: list[str]) -> dict[str, Any]:
        """获取文件/目录的当前状态.

        Returns:
            {"path": {"exists": bool, "type": "file|dir", "mode": "755", ...}}
        """
        state: dict[str, Any] = {}
        for p in paths:
            path = Path(p)
            if not path.exists():
                state[p] = {"exists": False}
                continue
            try:
                stat = path.stat()
                state[p] = {
                    "exists": True,
                    "type": "dir" if path.is_dir() else "file",
                    "size": stat.st_size,
                    "mode": oct(stat.st_mode)[-3:],
                    "modified": datetime.datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat(),
                }
            except OSError:
                state[p] = {"exists": True, "error": "unreadable"}
        return state

    def create_snapshot(
        self,
        operation: str,
        risk_level: str = "IRREVERSIBLE",
        paths: list[str] | None = None,
        user: str = "",
    ) -> SnapshotRecord:
        """创建操作前快照.

        Args:
            operation: 触发快照的操作描述
            risk_level: 风险等级
            paths: 需要快照的文件/目录路径
            user: 触发用户

        Returns:
            SnapshotRecord
        """
        snap_id = f"snap-{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now().isoformat()
        snap_dir = self.base_dir / snap_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        # 记录文件状态
        files_before: list[str] = []
        paths = paths or []

        if paths:
            # 备份文件内容
            backup_dir = snap_dir / "files"
            backup_dir.mkdir(exist_ok=True)

            for p in paths:
                src = Path(p)
                if not src.exists():
                    continue
                try:
                    # 计算相对路径用于备份
                    rel = src.absolute().as_posix().lstrip("/").replace("/", "_")
                    dst = backup_dir / rel

                    if src.is_file():
                        shutil.copy2(str(src), str(dst))
                        files_before.append(p)
                    elif src.is_dir():
                        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
                        files_before.append(p)
                except (OSError, shutil.Error) as exc:
                    # 记录失败但不中断
                    (snap_dir / "errors.log").open("a").write(
                        f"[{now}] Failed to backup {p}: {exc}\n"
                    )

        # 记录文件状态元数据
        state = self._get_file_state(paths or [])
        (snap_dir / "file_state.json").write_text(
            json.dumps(state, indent=2, ensure_ascii=False)
        )

        # 记录操作日志
        (snap_dir / "snapshot.json").write_text(
            json.dumps({
                "id": snap_id,
                "created_at": now,
                "operation": operation,
                "risk_level": risk_level,
                "user": user,
                "paths": paths,
                "files_backed_up": files_before,
            }, indent=2, ensure_ascii=False)
        )

        record = SnapshotRecord(
            id=snap_id,
            created_at=now,
            operation=operation,
            risk_level=risk_level,
            user=user,
            path=str(snap_dir),
            files_before=files_before,
        )

        # 更新索引
        self._index[snap_id] = record.to_dict()
        self._save_index()

        return record

    def list_snapshots(self, limit: int = 20) -> list[SnapshotRecord]:
        """列出最近快照."""
        records = []
        for snap_id, data in sorted(
            self._index.items(),
            key=lambda x: x[1].get("created_at", ""),
            reverse=True,
        )[:limit]:
            records.append(SnapshotRecord(
                id=snap_id,
                created_at=data.get("created_at", ""),
                operation=data.get("operation", ""),
                risk_level=data.get("risk_level", ""),
                user=data.get("user", ""),
                path=data.get("path", ""),
                files_before=data.get("files_before", []),
            ))
        return records

    def get_snapshot(self, snap_id: str) -> SnapshotRecord | None:
        """获取单个快照记录."""
        data = self._index.get(snap_id)
        if not data:
            return None
        return SnapshotRecord(
            id=snap_id,
            created_at=data.get("created_at", ""),
            operation=data.get("operation", ""),
            risk_level=data.get("risk_level", ""),
            user=data.get("user", ""),
            path=data.get("path", ""),
            files_before=data.get("files_before", []),
        )

    def restore_snapshot(self, snap_id: str) -> dict[str, Any]:
        """回滚到快照状态.

        Args:
            snap_id: 快照ID

        Returns:
            {"success": bool, "restored": [文件列表], "failed": [失败列表]}
        """
        record = self.get_snapshot(snap_id)
        if not record:
            return {"success": False, "error": f"快照不存在: {snap_id}"}

        snap_dir = Path(record.path) if record.path else self.base_dir / snap_id
        backup_dir = snap_dir / "files"

        if not backup_dir.exists():
            return {"success": False, "error": "快照数据目录不存在"}

        restored: list[str] = []
        failed: list[str] = []

        # 记录回滚事件
        (snap_dir / "restore.log").open("a").write(
            f"[{datetime.datetime.now().isoformat()}] 开始回滚\n"
        )

        for original_path in record.files_before:
            try:
                rel = Path(original_path).absolute().as_posix().lstrip("/").replace("/", "_")
                backup_file = backup_dir / rel

                if not backup_file.exists():
                    failed.append(f"{original_path} (备份文件缺失)")
                    continue

                dst = Path(original_path)

                # 如果是目录，先删除再复制
                if dst.is_dir() and backup_file.is_dir():
                    shutil.rmtree(str(dst), ignore_errors=True)
                    shutil.copytree(str(backup_file), str(dst), dirs_exist_ok=True)
                elif backup_file.is_dir():
                    shutil.copytree(str(backup_file), str(dst), dirs_exist_ok=True)
                else:
                    # 确保目标目录存在
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(backup_file), str(dst))

                restored.append(original_path)

            except (OSError, shutil.Error) as exc:
                failed.append(f"{original_path}: {exc}")
                (snap_dir / "restore.log").open("a").write(
                    f"  FAILED: {original_path}: {exc}\n"
                )

        # 记录回滚完成
        (snap_dir / "restore.log").open("a").write(
            f"[{datetime.datetime.now().isoformat()}] 回滚完成: "
            f"成功={len(restored)}, 失败={len(failed)}\n"
        )

        # 更新索引
        if snap_id in self._index:
            self._index[snap_id]["restored_at"] = datetime.datetime.now().isoformat()
            self._index[snap_id]["restore_success"] = len(restored)
            self._index[snap_id]["restore_failed"] = len(failed)
            self._save_index()

        return {
            "success": len(failed) == 0,
            "snap_id": snap_id,
            "operation": record.operation,
            "restored": restored,
            "failed": failed,
            "restored_count": len(restored),
            "failed_count": len(failed),
        }

    def clean_old_snapshots(self, max_age_hours: int = 72) -> int:
        """清理过期快照."""
        now = datetime.datetime.now()
        removed = 0
        for snap_id, data in list(self._index.items()):
            try:
                created = datetime.datetime.fromisoformat(
                    data.get("created_at", "")
                )
                if (now - created).total_seconds() > max_age_hours * 3600:
                    snap_dir = self.base_dir / snap_id
                    if snap_dir.exists():
                        shutil.rmtree(str(snap_dir), ignore_errors=True)
                    del self._index[snap_id]
                    removed += 1
            except (ValueError, KeyError):
                continue
        if removed:
            self._save_index()
        return removed
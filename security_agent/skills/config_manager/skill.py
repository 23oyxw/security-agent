"""配置管理 Skill — 配置文件快照、变更检测、diff 展示、版本追踪."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from security_agent import config
from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.security.redact import redact_text
from security_agent.timeutil import now_iso

# ---- 默认监控的关键配置文件 ----
MANAGED_CONFIGS: dict[str, dict[str, str]] = {
    "/etc/ssh/sshd_config": {"category": "SSH", "description": "SSH 服务配置"},
    "/etc/passwd": {"category": "账户", "description": "用户信息"},
    "/etc/shadow": {"category": "账户", "description": "密码哈希"},
    "/etc/group": {"category": "账户", "description": "组信息"},
    "/etc/hosts": {"category": "网络", "description": "主机解析"},
    "/etc/resolv.conf": {"category": "网络", "description": "DNS 配置"},
    "/etc/fstab": {"category": "存储", "description": "文件系统挂载"},
    "/etc/crontab": {"category": "定时任务", "description": "系统 Cron"},
    "/etc/sudoers": {"category": "权限", "description": "Sudo 配置"},
    "/etc/sysctl.conf": {"category": "内核", "description": "内核参数"},
    "/etc/ntp.conf": {"category": "时间", "description": "NTP 时间同步"},
    "/etc/hostname": {"category": "系统", "description": "主机名"},
}

_SNAPSHOT_DIR = config.DATA_DIR / "config_snapshots"


class ConfigManagerSkill(SkillBase):
    """配置管理 Skill — 配置文件快照、变更检测、diff、版本追踪."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="config_manager",
            display_name="配置管理",
            description="关键配置文件快照、变更检测与 diff、版本追踪、合规检查",
            version="1.0.0",
            tags=("config", "snapshot", "diff", "compliance", "audit"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="config_snapshot",
                description="对关键配置文件生成快照（哈希+内容），用于变更检测",
                parameters={
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "string",
                            "description": "逗号分隔的文件路径（留空=默认列表）",
                            "default": "",
                        }
                    },
                    "required": [],
                },
                handler=self._tool_snapshot,
            ),
            ToolDef(
                name="config_diff",
                description="对比当前配置与最近一次快照的差异",
                parameters={
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "指定文件路径（留空=检查所有）",
                            "default": "",
                        }
                    },
                    "required": [],
                },
                handler=self._tool_diff,
            ),
            ToolDef(
                name="config_history",
                description="查看配置文件的变更历史（最近 N 次快照）",
                parameters={
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "文件路径"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["file"],
                },
                handler=self._tool_history,
            ),
            ToolDef(
                name="config_audit",
                description="审计所有受管配置文件的状态：存在性、权限、最后修改时间",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_audit,
            ),
            ToolDef(
                name="config_add_watch",
                description="添加一个配置文件到监控列表",
                parameters={
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "文件路径"},
                        "category": {"type": "string", "default": "自定义"},
                        "description": {"type": "string", "default": ""},
                    },
                    "required": ["file"],
                },
                handler=self._tool_add_watch,
            ),
        ]

    def get_rules(self) -> list[str]:
        return [
            "配置管理仅做快照和检测，不自动修改任何配置文件",
            "配置变更建议需说明影响范围，涉及系统配置必须人工确认",
        ]

    # ---- 核心功能 ----

    def _file_hash(self, path: str) -> str:
        """计算文件 SHA256."""
        try:
            data = Path(path).read_bytes()
            return hashlib.sha256(data).hexdigest()[:16]
        except (OSError, PermissionError):
            return ""

    def _file_stat(self, path: str) -> dict[str, Any]:
        """获取文件元信息."""
        p = Path(path)
        if not p.exists():
            return {"exists": False, "path": path}
        try:
            st = p.stat()
            return {
                "exists": True,
                "path": path,
                "size": st.st_size,
                "mode": oct(st.st_mode)[-4:],
                "uid": st.st_uid,
                "gid": st.st_gid,
                "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "hash": self._file_hash(path),
            }
        except (OSError, PermissionError):
            return {"exists": True, "path": path, "error": "permission_denied"}

    def take_snapshot(self, files: list[str] | None = None) -> dict[str, Any]:
        """生成配置文件快照."""
        _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        targets = files or list(MANAGED_CONFIGS.keys())
        ts = now_iso()
        ts_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        snapshots: list[dict[str, Any]] = []
        for path in targets:
            info = self._file_stat(path)
            cat_info = MANAGED_CONFIGS.get(path, {"category": "自定义", "description": ""})

            record = {
                **info,
                "category": cat_info["category"],
                "description": cat_info["description"],
                "snapshot_ts": ts,
            }

            # 保存文件内容到快照目录
            if info.get("exists") and info.get("hash"):
                snap_file = _SNAPSHOT_DIR / f"{info['hash']}.content"
                if not snap_file.exists():
                    try:
                        content = Path(path).read_text(encoding="utf-8", errors="replace")
                        snap_file.write_text(content, encoding="utf-8")
                    except (OSError, PermissionError):
                        pass

            snapshots.append(record)

        # 保存快照元数据
        meta_path = _SNAPSHOT_DIR / f"snapshot_{ts_id}.json"
        meta_path.write_text(
            json.dumps({"ts": ts, "files": snapshots}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 更新 latest 链接
        latest = _SNAPSHOT_DIR / "latest.json"
        latest.write_text(
            json.dumps({"ts": ts, "file": str(meta_path), "files": snapshots}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {"timestamp": ts, "snapshot_id": ts_id, "files": len(snapshots), "details": snapshots}

    def diff_current_vs_snapshot(self, target_file: str = "") -> list[dict[str, Any]]:
        """对比当前配置与最近快照."""
        latest = _SNAPSHOT_DIR / "latest.json"
        if not latest.exists():
            return [{"error": "无快照，请先运行 config_snapshot"}]

        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return [{"error": "快照数据损坏"}]

        changes: list[dict[str, Any]] = []
        for snap in data.get("files", []):
            path = snap.get("path", "")
            if target_file and path != target_file:
                continue

            current = self._file_stat(path)
            if not current.get("exists") and snap.get("exists"):
                changes.append({
                    "path": path,
                    "change": "deleted",
                    "severity": "严重",
                    "old_hash": snap.get("hash", ""),
                })
                continue

            if current.get("exists") and not snap.get("exists"):
                changes.append({
                    "path": path,
                    "change": "new",
                    "severity": "中",
                    "new_hash": current.get("hash", ""),
                })
                continue

            if current.get("hash") != snap.get("hash"):
                change: dict[str, Any] = {
                    "path": path,
                    "change": "modified",
                    "severity": "高",
                    "old_hash": snap.get("hash", ""),
                    "new_hash": current.get("hash", ""),
                    "old_mtime": snap.get("mtime", ""),
                    "new_mtime": current.get("mtime", ""),
                }
                # 生成 diff
                old_content = self._read_snapshot_content(snap.get("hash", ""))
                new_content = self._read_current_content(path)
                if old_content is not None and new_content is not None:
                    change["diff"] = self._simple_diff(old_content, new_content)
                changes.append(change)

        return changes

    def get_history(self, path: str, limit: int = 10) -> list[dict[str, Any]]:
        """查看文件变更历史."""
        if not _SNAPSHOT_DIR.exists():
            return []
        history: list[dict[str, Any]] = []
        for meta_file in sorted(_SNAPSHOT_DIR.glob("snapshot_*.json"), reverse=True):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                for f in data.get("files", []):
                    if f.get("path") == path:
                        history.append({
                            "ts": data.get("ts"),
                            "hash": f.get("hash"),
                            "size": f.get("size"),
                            "mode": f.get("mode"),
                            "mtime": f.get("mtime"),
                        })
                        break
            except (json.JSONDecodeError, OSError):
                continue
            if len(history) >= limit:
                break
        return history

    def audit_configs(self) -> dict[str, Any]:
        """审计所有受管配置文件."""
        results: list[dict[str, Any]] = []
        for path, meta in MANAGED_CONFIGS.items():
            info = self._file_stat(path)
            entry = {
                "path": path,
                "category": meta["category"],
                "description": meta["description"],
                **info,
            }
            # 检查权限
            if info.get("exists") and info.get("mode"):
                mode = info["mode"]
                if path in ("/etc/shadow", "/etc/gshadow") and mode not in ("0640", "0600"):
                    entry["permission_issue"] = f"权限 {mode}，应为 0640 或 0600"
                    entry["severity"] = "高"
                elif path == "/etc/sudoers" and mode != "0440":
                    entry["permission_issue"] = f"权限 {mode}，应为 0440"
                    entry["severity"] = "高"
            results.append(entry)

        issues = [r for r in results if r.get("permission_issue")]
        return {
            "timestamp": now_iso(),
            "total": len(results),
            "issues": len(issues),
            "files": results,
        }

    def add_watch(self, path: str, category: str = "自定义", description: str = "") -> dict[str, Any]:
        """动态添加配置文件到监控列表."""
        MANAGED_CONFIGS[path] = {
            "category": category,
            "description": description or f"用户添加: {path}",
        }
        return {"ok": True, "path": path, "total_managed": len(MANAGED_CONFIGS)}

    # ---- 辅助 ----

    def _read_snapshot_content(self, file_hash: str) -> str | None:
        if not file_hash:
            return None
        snap_file = _SNAPSHOT_DIR / f"{file_hash}.content"
        if snap_file.exists():
            try:
                return snap_file.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                return None
        return None

    def _read_current_content(self, path: str) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            return None

    @staticmethod
    def _simple_diff(old: str, new: str, max_lines: int = 50) -> list[str]:
        """简单 diff：逐行比较，返回变化行."""
        old_lines = old.splitlines()
        new_lines = new.splitlines()
        diff: list[str] = []
        max_check = min(len(old_lines), len(new_lines))
        for i in range(max_check):
            if old_lines[i] != new_lines[i]:
                diff.append(f"L{i+1} - {old_lines[i][:120]}")
                diff.append(f"L{i+1} + {new_lines[i][:120]}")
            if len(diff) >= max_lines:
                break
        # 长度差异
        if len(old_lines) != len(new_lines):
            diff.append(f"--- 行数: {len(old_lines)} → {len(new_lines)}")
        return diff[:max_lines]

    # ---- 工具处理器 ----

    async def _tool_snapshot(self, files: str = "") -> str:
        file_list = [f.strip() for f in files.split(",") if f.strip()] if files else None
        result = self.take_snapshot(file_list)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    async def _tool_diff(self, file: str = "") -> str:
        changes = self.diff_current_vs_snapshot(file)
        return json.dumps({"changes": changes, "count": len(changes)}, ensure_ascii=False, indent=2, default=str)

    async def _tool_history(self, file: str = "", limit: int = 10) -> str:
        history = self.get_history(file, limit)
        return json.dumps({"file": file, "history": history, "count": len(history)}, ensure_ascii=False, indent=2)

    async def _tool_audit(self) -> str:
        return json.dumps(self.audit_configs(), ensure_ascii=False, indent=2, default=str)

    async def _tool_add_watch(self, file: str = "", category: str = "自定义", description: str = "") -> str:
        return json.dumps(self.add_watch(file, category, description), ensure_ascii=False, indent=2)


# ---- 全局实例 ----
skill_instance = ConfigManagerSkill()
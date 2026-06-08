"""磁盘管理技能 — 空间分析、IO 监控、大文件扫描、备份恢复."""

from __future__ import annotations

import json
import os
import subprocess
import shutil
import time
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef


class DiskManagerSkill(SkillBase):
    """磁盘管理 Skill — 分区使用、IO 统计、大文件扫描、备份."""

    name = "disk_manager"
    display_name = "磁盘管理"

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="disk_manager",
            display_name="磁盘管理",
            description="磁盘空间分析、IO 监控、大文件扫描、备份恢复",
            version="1.0.0",
            tags=("disk", "storage", "backup", "iostat", "cleanup"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="disk_usage",
                description="获取所有分区磁盘使用情况，标注超过 85% 的告警分区",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._disk_usage,
            ),
            ToolDef(
                name="disk_io_stats",
                description="获取磁盘 IO 统计：读写量、IO 队列深度",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._io_stats,
            ),
            ToolDef(
                name="disk_large_files",
                description="扫描指定目录下最大文件（Top20），用于磁盘空间排查",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "default": "/"},
                        "min_size_mb": {"type": "integer", "default": 100, "minimum": 1},
                    },
                    "required": [],
                },
                handler=self._large_files,
            ),
            ToolDef(
                name="disk_cleanable",
                description="分析可清理目录：/tmp、/var/tmp、~/.cache 文件数与大小",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._cleanable,
            ),
            ToolDef(
                name="disk_backup",
                description="备份指定文件到 data/backups/，带时间戳",
                parameters={
                    "type": "object",
                    "properties": {"source": {"type": "string", "description": "源文件路径"}},
                    "required": ["source"],
                },
                handler=self._backup,
                auto_ok=False,
            ),
            ToolDef(
                name="disk_list_backups",
                description="列出已有备份文件",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._list_backups,
            ),
        ]

    def get_playbooks(self) -> list:
        return []

    def get_rules(self) -> list[str]:
        return ["磁盘使用率 > 85% 告警", "禁止删除 data/backups/ 下的备份文件"]

    async def on_alert(self, event: dict[str, Any]) -> dict[str, Any] | None:
        if event.get("type") == "disk" and event.get("percent", 0) > 85:
            return {
                "skill": "disk_manager",
                "action": "cleanup_suggested",
                "message": f"磁盘使用率 {event['percent']}%，建议运行 disk_large_files 排查或 disk_cleanable 清理",
            }
        return None

    async def healthcheck(self) -> dict[str, Any]:
        try:
            usage = shutil.disk_usage("/")
            return {"status": "ok", "disk_free_pct": round(usage.free / usage.total * 100, 1)}
        except Exception:
            return {"status": "error", "skill": "disk_manager"}

    # ---- Handlers ----

    async def _disk_usage(self) -> str:
        try:
            out = subprocess.run(["df", "-h", "-x", "tmpfs", "-x", "devtmpfs", "-x", "squashfs"], capture_output=True, text=True, timeout=10)
            if out.returncode != 0:
                return json.dumps({"error": out.stderr.strip()}, ensure_ascii=False)
            parts_list = []
            for line in out.stdout.split("\n")[1:]:
                parts = line.split()
                if len(parts) < 6:
                    continue
                try:
                    pct = float(parts[4].rstrip("%"))
                    parts_list.append({"device": parts[0], "mountpoint": parts[5], "size": parts[1], "used": parts[2], "free": parts[3], "percent": pct, "alert": pct > 85})
                except (ValueError, IndexError):
                    continue
            alerts = [p for p in parts_list if p["alert"]]
            return json.dumps({"partitions": sorted(parts_list, key=lambda x: -x["percent"]), "critical": alerts, "total": len(parts_list)}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _io_stats(self) -> str:
        try:
            out = subprocess.run(["iostat", "-x", "1", "1"], capture_output=True, text=True, timeout=15)
            if out.returncode == 0:
                return json.dumps({"source": "iostat", "raw": out.stdout[:2000]}, ensure_ascii=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        try:
            devices = []
            with open("/proc/diskstats") as f:
                for line in f.readlines()[:20]:
                    parts = line.strip().split()
                    if len(parts) >= 14:
                        devices.append({"device": parts[2], "reads": int(parts[3]), "writes": int(parts[7]), "read_mb": round(int(parts[5]) * 512 / 1024 / 1024, 2), "write_mb": round(int(parts[9]) * 512 / 1024 / 1024, 2), "io_in_progress": int(parts[11])})
            return json.dumps({"source": "/proc/diskstats", "devices": devices[:10]}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _large_files(self, path: str = "/", min_size_mb: int = 100) -> str:
        try:
            cmd = ["find", path, "-maxdepth", "4", "-type", "f", "-size", f"+{min_size_mb}M", "-printf", "%s %p\n"]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            files = []
            for line in out.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    size_bytes, fp = line.split(" ", 1)
                    files.append({"path": fp, "size_mb": round(int(size_bytes) / 1024 / 1024, 2)})
                except ValueError:
                    continue
            files.sort(key=lambda x: -x["size_mb"])
            top = files[:20]
            return json.dumps({"path": path, "min_size_mb": min_size_mb, "found": len(files), "top_20": top, "total_mb": round(sum(f["size_mb"] for f in top), 2)}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _cleanable(self) -> str:
        targets = ["/tmp", "/var/tmp", os.path.expanduser("~/.cache")]
        results = {}
        for p in targets:
            if not os.path.exists(p):
                results[p] = {"exists": False}
                continue
            try:
                total_size, count = 0, 0
                for root, dirs, files in os.walk(p):
                    for fn in files:
                        try:
                            total_size += os.path.getsize(os.path.join(root, fn))
                            count += 1
                        except OSError:
                            pass
                results[p] = {"exists": True, "file_count": count, "size_mb": round(total_size / 1024 / 1024, 2)}
            except Exception:
                results[p] = {"exists": True, "error": "permission_denied"}
        return json.dumps({"directories": results}, ensure_ascii=False, indent=2)

    async def _backup(self, source: str) -> str:
        backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        if not os.path.exists(source):
            return json.dumps({"error": f"源文件不存在: {source}"}, ensure_ascii=False)
        basename = os.path.basename(source)
        ts = time.strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(backup_dir, f"{basename}.{ts}")
        try:
            if os.path.isfile(source):
                shutil.copy2(source, dest)
            else:
                shutil.copytree(source, dest)
            return json.dumps({"source": source, "destination": dest, "success": True}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _list_backups(self) -> str:
        backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "backups")
        if not os.path.exists(backup_dir):
            return json.dumps({"backups": [], "total": 0}, ensure_ascii=False)
        files = []
        for fn in sorted(os.listdir(backup_dir), reverse=True)[:20]:
            fp = os.path.join(backup_dir, fn)
            files.append({"name": fn, "size_mb": round(os.path.getsize(fp) / 1024 / 1024, 2) if os.path.isfile(fp) else 0})
        return json.dumps({"backups": files, "total": len(files)}, ensure_ascii=False, indent=2)


skill_instance = DiskManagerSkill()

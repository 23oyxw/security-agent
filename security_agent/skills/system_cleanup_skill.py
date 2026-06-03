"""系统垃圾清理 Skill — 扫描可清理项、分类报告、安全确认后执行."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef


# ---- 清理项定义 ----
@dataclass
class CleanupItem:
    category: str          # 分类: apt / journal / tmp / pip / docker / kernel / trash / log
    name: str              # 人类可读名称
    description: str       # 清理说明
    path: str = ""         # 文件系统路径（如适用）
    command_safe: str = ""  # 安全清理命令（需要 sudo?）
    estimated_bytes: int = 0
    files_count: int = 0
    risky: bool = False     # 是否高风险（需确认）


CATEGORIES = [
    "apt",
    "journal",
    "tmp",
    "pip",
    "docker",
    "kernel",
    "trash",
    "log",
]


def _run(cmd: str, timeout: float = 30) -> tuple[int, str, str]:
    """运行 shell 命令，返回 (rc, stdout, stderr)."""
    try:
        p = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
        )
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def _parse_size(du_output: str) -> int:
    """从 du -sb 输出解析字节数."""
    try:
        return int(du_output.strip().split()[0])
    except (ValueError, IndexError):
        return 0


def _scan_apt() -> CleanupItem:
    """APT 缓存目录大小."""
    item = CleanupItem(
        category="apt",
        name="APT 缓存",
        description="apt 下载的 deb 包缓存 (/var/cache/apt/archives)",
        path="/var/cache/apt/archives",
        command_safe="apt-get clean",
    )
    rc, out, _ = _run("du -sb /var/cache/apt/archives 2>/dev/null || echo '0'")
    item.estimated_bytes = _parse_size(out)
    if os.path.isdir(item.path):
        item.files_count = len(os.listdir(item.path))
    return item


def _scan_journal() -> CleanupItem:
    """Journal 日志占用."""
    item = CleanupItem(
        category="journal",
        name="Journal 日志",
        description="systemd journal 日志 (/var/log/journal)，可清理至 200M",
        command_safe="journalctl --vacuum-size=200M",
    )
    # 尝试获取 journal 磁盘使用
    rc, out, _ = _run("journalctl --disk-usage 2>/dev/null || echo '0'")
    if "bytes" in out:
        try:
            # "Archived and active journals take up 256.0M on disk."
            for part in out.split():
                if part.endswith("M") or part.endswith("G") or part.endswith("K"):
                    num = part.rstrip("MGK")
                    mul = {"K": 1024, "M": 1024**2, "G": 1024**3}.get(part[-1], 0)
                    item.estimated_bytes = int(float(num) * mul)
                    break
        except (ValueError, IndexError):
            pass
    if item.estimated_bytes == 0:
        rc, out, _ = _run("du -sb /var/log/journal 2>/dev/null || echo '0'")
        item.estimated_bytes = _parse_size(out)
    return item


def _scan_tmp() -> CleanupItem:
    """/tmp 旧文件."""
    item = CleanupItem(
        category="tmp",
        name="临时文件",
        description="/tmp 中超过 7 天的文件",
        path="/tmp",
        command_safe="find /tmp -type f -mtime +7 -delete && find /tmp -type d -empty -mtime +7 -delete 2>/dev/null",
        risky=True,
    )
    rc, out, _ = _run("find /tmp -type f -mtime +7 -printf '%s\n' 2>/dev/null | awk '{s+=$1;c++} END{print s,c}'")
    parts = out.strip().split()
    if len(parts) >= 2:
        item.estimated_bytes = int(parts[0])
        item.files_count = int(parts[1])
    return item


def _scan_pip() -> CleanupItem:
    """pip 缓存."""
    item = CleanupItem(
        category="pip",
        name="pip 缓存",
        description="pip 下载的 wheel/sdist 缓存 (~/.cache/pip)",
        path=os.path.expanduser("~/.cache/pip"),
        command_safe="pip cache purge 2>/dev/null || rm -rf ~/.cache/pip",
    )
    pip_cache = os.path.expanduser("~/.cache/pip")
    rc, out, _ = _run(f"du -sb {pip_cache} 2>/dev/null || echo '0'")
    item.estimated_bytes = _parse_size(out)
    return item


def _scan_docker() -> CleanupItem | None:
    """Docker 悬空镜像和停止容器."""
    rc, out, _ = _run("docker info 2>/dev/null")
    if rc != 0:
        return None
    item = CleanupItem(
        category="docker",
        name="Docker 悬空资源",
        description="悬空镜像、停止的容器、未使用的构建缓存",
        command_safe="docker system prune -f 2>/dev/null",
        risky=True,
    )
    rc, out, _ = _run("docker system df --format '{{.Size}}' 2>/dev/null")
    # 粗略合计
    total = 0
    for s in out.strip().split("\n"):
        try:
            s = s.upper().replace("GB", "G").replace("MB", "M").replace("KB", "K")
            n = float(s[:-1])
            mul = {"K": 1024, "M": 1024**2, "G": 1024**3}.get(s[-1], 0)
            total += int(n * mul)
        except (ValueError, IndexError):
            pass
    item.estimated_bytes = total
    return item


def _scan_kernel() -> CleanupItem:
    """旧内核."""
    item = CleanupItem(
        category="kernel",
        name="旧内核",
        description="已卸载但残留的内核包，可 apt autoremove 清理",
        command_safe="apt-get autoremove --purge -y 2>/dev/null",
        risky=True,
    )
    rc, out, _ = _run("dpkg -l 'linux-*' 2>/dev/null | grep '^rc' | wc -l")
    try:
        item.files_count = int(out.strip())
    except ValueError:
        pass
    if item.files_count > 0:
        item.estimated_bytes = item.files_count * 200 * 1024 * 1024  # 每个内核约 200M
    return item


def _scan_trash() -> CleanupItem:
    """用户回收站."""
    trash_dirs = [
        os.path.expanduser("~/.local/share/Trash"),
    ]
    total_bytes = 0
    total_files = 0
    for d in trash_dirs:
        if os.path.isdir(d):
            rc, out, _ = _run(f"du -sb {d} 2>/dev/null || echo '0'")
            total_bytes += _parse_size(out)
            # 统计 files 目录
            files_dir = os.path.join(d, "files")
            if os.path.isdir(files_dir):
                try:
                    total_files += sum(1 for _ in Path(files_dir).rglob("*") if _.is_file())
                except (PermissionError, OSError):
                    pass
    item = CleanupItem(
        category="trash",
        name="回收站",
        description="用户回收站 (~/.local/share/Trash)",
        path=trash_dirs[0],
        command_safe=f"rm -rf {trash_dirs[0]}/files/* {trash_dirs[0]}/info/* 2>/dev/null",
        estimated_bytes=total_bytes,
        files_count=total_files,
        risky=True,
    )
    return item


def _scan_old_logs() -> CleanupItem:
    """/var/log 大日志文件."""
    item = CleanupItem(
        category="log",
        name="旧日志文件",
        description="/var/log 中超过 30 天的 .log 文件（旋转压缩后仍保留的）",
        path="/var/log",
        command_safe="find /var/log -name '*.log.*.gz' -mtime +30 -delete 2>/dev/null",
    )
    rc, out, _ = _run(
        "find /var/log -type f -size +10M -printf '%s\n' 2>/dev/null | awk '{s+=$1;c++} END{printf \"%.0f %d\", s, c}'"
    )
    parts = out.strip().split()
    if len(parts) >= 2:
        item.estimated_bytes = int(float(parts[0]))
        item.files_count = int(parts[1])
    return item


SCANNERS = {
    "apt": _scan_apt,
    "journal": _scan_journal,
    "tmp": _scan_tmp,
    "pip": _scan_pip,
    "docker": _scan_docker,
    "kernel": _scan_kernel,
    "trash": _scan_trash,
    "log": _scan_old_logs,
}

EXECUTORS: dict[str, str] = {
    "apt": "apt-get clean 2>/dev/null",
    "journal": "journalctl --vacuum-size=200M 2>/dev/null",
    "tmp": "find /tmp -type f -mtime +7 -delete 2>/dev/null; find /tmp -type d -empty -mtime +7 -delete 2>/dev/null",
    "pip": "pip cache purge 2>/dev/null || rm -rf ~/.cache/pip/* 2>/dev/null",
    "docker": "docker system prune -f 2>/dev/null",
    "kernel": "apt-get autoremove --purge -y 2>/dev/null",
    "trash": "rm -rf ~/.local/share/Trash/files/* ~/.local/share/Trash/info/* 2>/dev/null",
    "log": "find /var/log -name '*.log.*.gz' -mtime +30 -delete 2>/dev/null",
}

EXECUTORS_SAFE: dict[str, str] = {
    "apt": "apt-get clean 2>/dev/null",
    "journal": "journalctl --vacuum-size=200M 2>/dev/null",
    "tmp": "echo '[DRY-RUN] find /tmp -type f -mtime +7 -delete'",
    "pip": "echo '[DRY-RUN] pip cache purge'",
    "docker": "echo '[DRY-RUN] docker system prune -f'",
    "kernel": "echo '[DRY-RUN] apt-get autoremove --purge -y'",
    "trash": "echo '[DRY-RUN] rm -rf ~/.local/share/Trash'",
    "log": "echo '[DRY-RUN] 清理大日志文件'",
}


class SystemCleanupSkill(SkillBase):
    """系统垃圾清理 Skill — 扫描、报告、安全执行."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="system_cleanup",
            display_name="系统清理",
            description="扫描系统可清理项（APT/Journal/tmp/pip/Docker/内核/回收站/日志），分类报告并安全执行清理",
            version="1.0.0",
            tags=("cleanup", "maintenance", "system", "disk"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="system_cleanup_scan",
                description=(
                    "扫描所有可清理项并报告预估空间，不执行任何清理。"
                    f"覆盖分类: {', '.join(CATEGORIES)}。返回每项的名称、预估字节数、文件数、风险等级。"
                ),
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_scan,
                auto_ok=True,
            ),
            ToolDef(
                name="system_cleanup_run",
                description=(
                    "执行系统清理。可指定分类或全部清理。高风险项(tmp/docker/kernel/trash)默认仅报告不执行。"
                    f"可选 categories 参数指定要清理的分类列表（{', '.join(CATEGORIES)} 的子集），"
                    "不传则清理所有安全类(apt/journal/log)。"
                    "设置 confirm_all=true 才执行高风险项。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": f"要清理的分类列表，如 ['apt','journal']。不传则清理所有安全类",
                        },
                        "confirm_all": {
                            "type": "boolean",
                            "description": "是否确认执行高风险项（tmp/docker/kernel/trash）。默认 false",
                            "default": False,
                        },
                    },
                    "required": [],
                },
                handler=self._tool_run,
                auto_ok=False,
            ),
        ]

    # ---- 扫描逻辑 ----

    def scan_all(self) -> dict[str, Any]:
        """扫描所有清理项."""
        items: list[dict[str, Any]] = []
        total_bytes = 0
        errors: list[str] = []

        for cat in CATEGORIES:
            try:
                result = SCANNERS[cat]()
                if result is None:
                    continue
                items.append({
                    "category": result.category,
                    "name": result.name,
                    "description": result.description,
                    "estimated_bytes": result.estimated_bytes,
                    "estimated_mb": round(result.estimated_bytes / (1024**2), 2),
                    "estimated_human": _human_size(result.estimated_bytes),
                    "files_count": result.files_count,
                    "risky": result.risky,
                    "command": result.command_safe,
                })
                total_bytes += result.estimated_bytes
            except Exception as e:
                errors.append(f"{cat}: {e}")

        items.sort(key=lambda x: x["estimated_bytes"], reverse=True)

        return {
            "items": items,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024**2), 2),
            "total_human": _human_size(total_bytes),
            "safe_items": [i for i in items if not i["risky"]],
            "risky_items": [i for i in items if i["risky"]],
            "recommendation": self._recommend(items),
            "errors": errors,
            "timestamp": int(time.time()),
        }

    def _recommend(self, items: list[dict[str, Any]]) -> str:
        """根据扫描结果给出建议."""
        if not items:
            return "未发现可清理项"
        total_mb = sum(i["estimated_mb"] for i in items)
        safe_mb = sum(i["estimated_mb"] for i in items if not i["risky"])
        risky_count = sum(1 for i in items if i["risky"] and i["estimated_bytes"] > 0)

        if total_mb < 1:
            return "系统很干净，无需清理"
        parts = [f"共可释放约 {_human_size(int(total_mb * 1024**2))}"]
        if safe_mb > 0:
            parts.append(f"安全清理 {_human_size(int(safe_mb * 1024**2))}（apt/journal/log 等）")
        if risky_count > 0:
            parts.append(f"{risky_count} 项高风险需确认（tmp/docker/kernel/trash）")
        return "。".join(parts)

    # ---- 执行逻辑 ----

    def execute(self, categories: list[str] | None, confirm_all: bool = False) -> dict[str, Any]:
        """执行清理."""
        targets = list(categories) if categories else ["apt", "journal", "log"]
        unknown = [c for c in targets if c not in CATEGORIES]
        if unknown:
            return {"ok": False, "error": f"未知分类: {unknown}"}

        high_risk = {"tmp", "docker", "kernel", "trash"}
        blocked = [c for c in targets if c in high_risk and not confirm_all]
        if blocked:
            return {
                "ok": False,
                "blocked": True,
                "message": f"以下为高风险项，需 confirm_all=true: {blocked}",
                "blocked_categories": blocked,
                "hint": "设置 confirm_all=true 确认执行高风险清理",
            }

        results: list[dict[str, Any]] = []
        freed_bytes = 0
        for cat in targets:
            cmd = EXECUTORS[cat]
            rc, stdout, stderr = _run(cmd, timeout=120)
            results.append({
                "category": cat,
                "command": cmd,
                "exit_code": rc,
                "stdout": stdout[:500],
                "stderr": stderr[:500],
                "ok": rc == 0,
            })
            if rc == 0:
                freed_bytes += 0  # 实际难以精确计量

        return {
            "ok": True,
            "results": results,
            "executed": len(targets),
            "succeeded": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]),
        }

    # ---- 工具处理器 ----

    async def _tool_scan(self) -> str:
        result = self.scan_all()
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_run(self, categories: list[str] | None = None, confirm_all: bool = False) -> str:
        result = self.execute(categories, confirm_all)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ---- 告警回调 ----

    async def on_alert(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """响应磁盘告警 — 自动扫描并提供清理建议."""
        etype = str(event.get("type", ""))
        if "磁盘" not in etype and "disk" not in etype.lower():
            return None
        scan = self.scan_all()
        return {
            "action": "cleanup_scan",
            "scan": scan,
            "safe_to_clean_cmd": "system_cleanup_run(categories=['apt','journal','log'])",
        }


def _human_size(b: int) -> str:
    if b == 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# Skill 自动发现入口
skill_instance = SystemCleanupSkill()

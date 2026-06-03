"""敏感文件访问规则引擎 — 检测敏感文件变更和异常访问."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class FileImportance(str, Enum):
    """文件重要性等级."""
    CRITICAL = "critical"   # 系统关键配置
    HIGH = "high"           # 安全相关文件
    MEDIUM = "medium"       # 应用配置文件
    LOW = "low"             # 一般文件


class FileChangeType(str, Enum):
    """文件变更类型."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    PERMISSION_CHANGED = "permission_changed"
    OWNER_CHANGED = "owner_changed"


@dataclass
class FileSnapshot:
    """文件快照."""
    path: str
    size: int
    mtime: float
    mode: int
    owner: str
    sha256: str
    snapshot_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "mode": self.mode,
            "owner": self.owner,
            "sha256": self.sha256,
            "snapshot_at": self.snapshot_at,
        }


@dataclass
class FileChangeEvent:
    """文件变更事件."""
    path: str
    change_type: FileChangeType
    importance: FileImportance
    old_snapshot: Optional[FileSnapshot] = None
    new_snapshot: Optional[FileSnapshot] = None
    rule_id: str = ""
    description: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "change_type": self.change_type.value,
            "importance": self.importance.value,
            "old_snapshot": self.old_snapshot.to_dict() if self.old_snapshot else None,
            "new_snapshot": self.new_snapshot.to_dict() if self.new_snapshot else None,
            "rule_id": self.rule_id,
            "description": self.description,
            "detected_at": self.detected_at,
        }


@dataclass
class FileRule:
    """敏感文件监控规则."""
    rule_id: str
    name: str
    pattern: str  # glob 模式或正则
    importance: FileImportance
    description: str = ""
    check_content: bool = False
    check_permission: bool = True
    check_owner: bool = True
    max_size_bytes: int = 0  # 0 表示不限制
    enabled: bool = True

    def matches(self, filepath: str) -> bool:
        """判断文件路径是否匹配此规则."""
        if not self.enabled:
            return False
        # 支持 glob 模式
        from fnmatch import fnmatch
        return fnmatch(filepath, self.pattern) or fnmatch(os.path.basename(filepath), self.pattern)


# ============================================================
# 预定义敏感文件规则
# ============================================================

DEFAULT_FILE_RULES: List[FileRule] = [
    # CRITICAL - 系统关键文件
    FileRule(
        rule_id="FR-001",
        name="SSH 密钥文件",
        pattern="/etc/ssh/*_key",
        importance=FileImportance.CRITICAL,
        description="SSH 私钥文件，泄露可导致远程未授权访问",
        check_content=False,
        check_permission=True,
        check_owner=True,
    ),
    FileRule(
        rule_id="FR-002",
        name="shadow 密码文件",
        pattern="/etc/shadow",
        importance=FileImportance.CRITICAL,
        description="用户密码哈希文件，修改可能导致账户安全风险",
        check_content=False,
        check_permission=True,
        check_owner=True,
    ),
    FileRule(
        rule_id="FR-003",
        name="sudoers 配置",
        pattern="/etc/sudoers",
        importance=FileImportance.CRITICAL,
        description="sudo 权限配置，错误修改可能导致权限提升",
        check_content=False,
        check_permission=True,
    ),
    FileRule(
        rule_id="FR-004",
        name="SSH 服务配置",
        pattern="/etc/ssh/sshd_config",
        importance=FileImportance.CRITICAL,
        description="SSH 服务配置，修改可能影响远程访问安全",
        check_content=True,
        check_permission=True,
    ),
    FileRule(
        rule_id="FR-005",
        name="crontab 文件",
        pattern="/etc/crontab",
        importance=FileImportance.CRITICAL,
        description="系统定时任务配置，篡改可能植入持久化后门",
    ),
    FileRule(
        rule_id="FR-006",
        name="PAM 认证配置",
        pattern="/etc/pam.d/*",
        importance=FileImportance.CRITICAL,
        description="PAM 认证模块配置，修改可绕过认证",
    ),
    FileRule(
        rule_id="FR-007",
        name="hosts 文件",
        pattern="/etc/hosts",
        importance=FileImportance.HIGH,
        description="DNS 解析文件，篡改可实现钓鱼攻击",
    ),
    # HIGH - 安全相关文件
    FileRule(
        rule_id="FR-010",
        name="环境变量文件 (.env)",
        pattern="*/.env",
        importance=FileImportance.HIGH,
        description="应用环境变量文件，通常包含 API 密钥和数据库密码",
        check_content=True,
    ),
    FileRule(
        rule_id="FR-011",
        name="环境变量文件 (.env.local)",
        pattern="*/.env.local",
        importance=FileImportance.HIGH,
        description="本地环境变量文件，包含本地开发敏感配置",
    ),
    FileRule(
        rule_id="FR-012",
        name="配置文件 (config.yaml/yml)",
        pattern="*/config.yaml",
        importance=FileImportance.MEDIUM,
        description="应用配置文件，可能包含敏感信息",
    ),
    FileRule(
        rule_id="FR-013",
        name="数据库配置",
        pattern="*/database*.yml",
        importance=FileImportance.HIGH,
        description="数据库连接配置，包含数据库凭据",
    ),
    FileRule(
        rule_id="FR-014",
        name="SSL/TLS 证书私钥",
        pattern="*.key",
        importance=FileImportance.CRITICAL,
        description="SSL/TLS 私钥文件",
    ),
    FileRule(
        rule_id="FR-015",
        name="PKCS 私钥",
        pattern="*.pem",
        importance=FileImportance.HIGH,
        description="PEM 格式证书/密钥文件",
    ),
    FileRule(
        rule_id="FR-020",
        name="Git 配置文件",
        pattern="*/.git/config",
        importance=FileImportance.MEDIUM,
        description="Git 仓库配置，可能包含凭据",
    ),
    FileRule(
        rule_id="FR-021",
        name="SSH known_hosts",
        pattern="*/.ssh/known_hosts",
        importance=FileImportance.MEDIUM,
        description="已知主机列表",
    ),
    FileRule(
        rule_id="FR-022",
        name="SSH authorized_keys",
        pattern="*/.ssh/authorized_keys",
        importance=FileImportance.HIGH,
        description="SSH 公钥授权列表，添加公钥可实现未授权远程登录",
        check_content=True,
    ),
    FileRule(
        rule_id="FR-023",
        name="Shell 历史记录",
        pattern="*/.bash_history",
        importance=FileImportance.MEDIUM,
        description="Shell 命令历史记录，可能包含敏感命令和密码",
    ),
    FileRule(
        rule_id="FR-025",
        name="Docker 配置",
        pattern="*/docker-compose*.yml",
        importance=FileImportance.MEDIUM,
        description="Docker Compose 配置，可能包含数据库密码等敏感信息",
    ),
]


def compute_file_hash(filepath: str) -> str:
    """计算文件 SHA-256 哈希值."""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, FileNotFoundError, OSError):
        return ""


def get_file_owner(filepath: str) -> str:
    """获取文件所有者."""
    try:
        import pwd
        stat = os.stat(filepath)
        return pwd.getpwuid(stat.st_uid).pw_name
    except (ImportError, KeyError, OSError):
        return "unknown"


def take_snapshot(filepath: str) -> Optional[FileSnapshot]:
    """对文件拍摄快照."""
    try:
        stat = os.stat(filepath)
        return FileSnapshot(
            path=filepath,
            size=stat.st_size,
            mtime=stat.st_mtime,
            mode=stat.st_mode,
            owner=get_file_owner(filepath),
            sha256=compute_file_hash(filepath),
        )
    except (FileNotFoundError, PermissionError, OSError):
        return None


class FileRuleEngine:
    """敏感文件规则引擎 — 扫描和监控敏感文件变更."""

    def __init__(self, rules: Optional[List[FileRule]] = None, scan_root: str = "/"):
        self.rules = rules or DEFAULT_FILE_RULES
        self.scan_root = scan_root
        self._snapshots: Dict[str, FileSnapshot] = {}  # filepath -> snapshot
        self._events: List[FileChangeEvent] = []
        self._known_paths: Set[str] = set()

    def scan_sensitive_files(self, max_depth: int = 3) -> List[Dict[str, Any]]:
        """扫描系统中匹配规则的敏感文件.

        Returns:
            匹配的文件列表，包含文件信息和对应的规则
        """
        results: List[Dict[str, Any]] = []
        checked = 0

        for rule in self.rules:
            if not rule.enabled:
                continue

            # 对 glob 模式进行展开匹配
            pattern = rule.pattern
            matched_files = self._expand_pattern(pattern)

            for filepath in matched_files:
                checked += 1
                snapshot = take_snapshot(filepath)
                if not snapshot:
                    continue

                result = {
                    "filepath": filepath,
                    "rule_id": rule.rule_id,
                    "rule_name": rule.name,
                    "importance": rule.importance.value,
                    "description": rule.description,
                    "size": snapshot.size,
                    "owner": snapshot.owner,
                    "mode": oct(snapshot.mode),
                    "sha256": snapshot.sha256[:16],
                    "issues": [],
                }

                # 权限检查
                if rule.check_permission and snapshot.mode:
                    perm_issues = self._check_permissions(filepath, snapshot.mode, rule.importance)
                    result["issues"].extend(perm_issues)

                # 所有者检查
                if rule.check_owner and snapshot.owner == "root":
                    pass  # root 拥有关键文件是正常的

                # 内容检查（敏感关键字扫描）
                if rule.check_content:
                    content_issues = self._check_content(filepath)
                    result["issues"].extend(content_issues)

                # 大小检查
                if rule.max_size_bytes > 0 and snapshot.size > rule.max_size_bytes:
                    result["issues"].append({
                        "type": "oversized",
                        "detail": f"文件大小 {snapshot.size} 超过限制 {rule.max_size_bytes}",
                    })

                # 缓存快照
                self._snapshots[filepath] = snapshot
                self._known_paths.add(filepath)

                results.append(result)

        return results

    def check_changes(self) -> List[FileChangeEvent]:
        """检查已知文件是否发生变更.

        Returns:
            变更事件列表
        """
        events: List[FileChangeEvent] = []

        for filepath, old_snapshot in list(self._snapshots.items()):
            if not os.path.exists(filepath):
                # 文件被删除
                rule = self._find_rule_for_file(filepath)
                event = FileChangeEvent(
                    path=filepath,
                    change_type=FileChangeType.DELETED,
                    importance=rule.importance if rule else FileImportance.MEDIUM,
                    old_snapshot=old_snapshot,
                    rule_id=rule.rule_id if rule else "",
                    description=f"敏感文件被删除: {filepath}",
                )
                events.append(event)
                self._events.append(event)
                continue

            new_snapshot = take_snapshot(filepath)
            if not new_snapshot:
                continue

            # 检查内容变更
            if new_snapshot.sha256 != old_snapshot.sha256:
                rule = self._find_rule_for_file(filepath)
                event = FileChangeEvent(
                    path=filepath,
                    change_type=FileChangeType.MODIFIED,
                    importance=rule.importance if rule else FileImportance.MEDIUM,
                    old_snapshot=old_snapshot,
                    new_snapshot=new_snapshot,
                    rule_id=rule.rule_id if rule else "",
                    description=f"敏感文件内容变更: {filepath}",
                )
                events.append(event)
                self._events.append(event)
                # 更新快照
                self._snapshots[filepath] = new_snapshot

            # 检查权限变更
            if new_snapshot.mode != old_snapshot.mode:
                rule = self._find_rule_for_file(filepath)
                event = FileChangeEvent(
                    path=filepath,
                    change_type=FileChangeType.PERMISSION_CHANGED,
                    importance=rule.importance if rule else FileImportance.MEDIUM,
                    old_snapshot=old_snapshot,
                    new_snapshot=new_snapshot,
                    rule_id=rule.rule_id if rule else "",
                    description=(
                        f"文件权限变更: {filepath} "
                        f"{oct(old_snapshot.mode)} -> {oct(new_snapshot.mode)}"
                    ),
                )
                events.append(event)
                self._events.append(event)
                self._snapshots[filepath].mode = new_snapshot.mode

        return events

    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的变更事件."""
        return [e.to_dict() for e in self._events[-limit:]]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息."""
        importance_counts: Dict[str, int] = {}
        for snap in self._snapshots.values():
            rule = self._find_rule_for_file(snap.path)
            key = rule.importance.value if rule else "unknown"
            importance_counts[key] = importance_counts.get(key, 0) + 1

        return {
            "monitored_files": len(self._snapshots),
            "total_events": len(self._events),
            "active_rules": len([r for r in self.rules if r.enabled]),
            "importance_distribution": importance_counts,
        }

    def _expand_pattern(self, pattern: str) -> List[str]:
        """展开 glob 模式匹配文件."""
        import glob as glob_mod

        paths: List[str] = []

        # 直接匹配（绝对路径）
        if pattern.startswith("/"):
            paths = glob_mod.glob(pattern, recursive=False)

        # 相对路径模式 - 在常见目录中搜索
        else:
            search_dirs = [
                "/etc",
                "/root",
                os.path.expanduser("~"),
            ]
            for d in search_dirs:
                full_pattern = os.path.join(d, pattern)
                paths.extend(glob_mod.glob(full_pattern, recursive=True))

        return [p for p in paths if os.path.isfile(p)]

    def _find_rule_for_file(self, filepath: str) -> Optional[FileRule]:
        """找到匹配文件路径的规则."""
        for rule in self.rules:
            if rule.matches(filepath):
                return rule
        return None

    def _check_permissions(self, filepath: str, mode: int, importance: FileImportance) -> List[Dict[str, str]]:
        """检查文件权限是否合理."""
        issues = []
        # 关键文件不应全局可写
        if mode & 0o002:
            issues.append({
                "type": "world_writable",
                "detail": f"关键文件 {filepath} 全局可写 ({oct(mode)})，存在篡改风险",
            })
        # 关键文件不应全局可读（如 shadow）
        if importance == FileImportance.CRITICAL and mode & 0o004:
            if "shadow" in filepath or "key" in filepath:
                issues.append({
                    "type": "world_readable",
                    "detail": f"敏感文件 {filepath} 全局可读 ({oct(mode)})",
                })
        return issues

    def _check_content(self, filepath: str) -> List[Dict[str, str]]:
        """检查文件内容是否包含敏感信息."""
        issues = []
        sensitive_patterns = [
            (r'(?i)(api[_-]?key|api[_-]?secret)\s*[=:]\s*["\']?\w{16,}', "API 密钥"),
            (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']{6,}', "明文密码"),
            (r'(?i)(secret[_-]?key|signing[_-]?key)\s*[=:]\s*["\']?\w{16,}', "加密密钥"),
            (r'(?i)(access[_-]?token|auth[_-]?token)\s*[=:]\s*["\']?\w{16,}', "访问令牌"),
            (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', "私钥"),
        ]

        try:
            with open(filepath, "r", errors="ignore") as f:
                content = f.read(1024 * 100)  # 只读前 100KB
                for pattern, desc in sensitive_patterns:
                    if re.search(pattern, content):
                        issues.append({
                            "type": "sensitive_content",
                            "detail": f"文件 {filepath} 中检测到{desc}",
                        })
        except (PermissionError, OSError):
            pass

        return issues


# ============================================================
# 全局单例
# ============================================================

_file_rule_engine: Optional[FileRuleEngine] = None


def get_file_rule_engine() -> FileRuleEngine:
    """获取全局文件规则引擎实例."""
    global _file_rule_engine
    if _file_rule_engine is None:
        _file_rule_engine = FileRuleEngine()
    return _file_rule_engine


def scan_sensitive_files() -> List[Dict[str, Any]]:
    """便捷函数：扫描敏感文件."""
    engine = get_file_rule_engine()
    return engine.scan_sensitive_files()


def check_file_changes() -> List[Dict[str, Any]]:
    """便捷函数：检查文件变更."""
    engine = get_file_rule_engine()
    events = engine.check_changes()
    return [e.to_dict() for e in events]
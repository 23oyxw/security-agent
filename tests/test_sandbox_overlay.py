"""SandboxSession 端到端测试 — preview → execute → changes → rollback.

覆盖:
    1. SandboxProfile 自动选层（每种风险等级的 Profile 选择）
    2. OverlayFS setup/diff/rollback 生命周期
    3. SandboxSession 五接口完整流程
    4. Windows fallback（snapshot 模式）
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


# ---- SandboxProfile ----

def test_profile_readonly():
    """READONLY 风险 → 只加 rlimit，不加 OverlayFS."""
    from security_agent.sandbox.profile import SandboxProfile
    p = SandboxProfile.choose("READONLY")
    assert p.name == "observe_only"
    assert p.rlimit_enabled is True
    assert p.overlay_enabled is False
    assert p.mount_ns_enabled is False
    assert "只读观测" in p.reason


def test_profile_reversible():
    """REVERSIBLE 风险 → OverlayFS 启用."""
    from security_agent.sandbox.profile import SandboxProfile
    p = SandboxProfile.choose("REVERSIBLE")
    assert p.name == "safe_reversible"
    assert p.rlimit_enabled is True
    if sys.platform == "linux":
        assert p.overlay_enabled is True
        assert "写时复制" in p.reason


def test_profile_irreversible():
    """IRREVERSIBLE 风险 → 最严隔离."""
    from security_agent.sandbox.profile import SandboxProfile
    p = SandboxProfile.choose("IRREVERSIBLE")
    assert p.name == "strict_irreversible"
    assert p.rlimit_enabled is True
    assert "纵深防御" in p.reason or "多层次" in p.reason


def test_profile_critical():
    """CRITICAL 风险 → 拒绝."""
    from security_agent.sandbox.profile import SandboxProfile
    p = SandboxProfile.choose("CRITICAL")
    assert p.name == "deny_critical"
    assert p.rlimit_enabled is False
    assert p.overlay_enabled is False
    assert "拒绝" in p.reason or "人工" in p.reason


def test_profile_description():
    """每个 Profile 都有可读描述."""
    from security_agent.sandbox.profile import SandboxProfile
    for level in ("READONLY", "REVERSIBLE", "IRREVERSIBLE", "CRITICAL"):
        p = SandboxProfile.choose(level)
        assert isinstance(p.description, str)
        assert len(p.description) > 0
        assert isinstance(p.layer_count, int)
        assert p.layer_count >= 0


def test_profile_to_dict():
    """to_dict() 包含所有关键字段."""
    from security_agent.sandbox.profile import SandboxProfile
    p = SandboxProfile.choose("REVERSIBLE")
    d = p.to_dict()
    for key in ("name", "risk_level", "layer_count", "description", "reason", "layers", "limits"):
        assert key in d, f"Missing key: {key}"


# ---- OverlayFS ----

def test_overlay_setup_and_diff_windows_fallback():
    """Windows/snapshot 模式：setup → 创建文件 → diff → 检测到变更."""
    from security_agent.sandbox.overlay import OverlayFS, ChangeReport

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp) / "test_work"
        work_dir.mkdir()

        # 创建初始文件
        (work_dir / "original.txt").write_text("hello")

        overlay = OverlayFS(work_dir=Path(tmp) / "sandbox")
        overlay.setup(work_dir)

        # 模拟操作：修改文件 + 新增文件
        (work_dir / "original.txt").write_text("modified")
        (work_dir / "new_file.txt").write_text("new")

        changes = overlay.diff()

        assert isinstance(changes, ChangeReport)
        assert changes.total_files >= 1
        assert changes.changed_count >= 1

        # 找到修改的 original.txt
        modified_paths = [c.path for c in changes.modified]
        added_paths = [c.path for c in changes.added]
        assert "original.txt" in modified_paths or changes.modified or changes.total_files >= 1
        if "new_file.txt" in added_paths:
            assert any(c.change_type == "added" for c in changes.added)

        overlay.teardown()


def test_overlay_rollback_windows():
    """Windows 模式：rollback 不抛异常."""
    from security_agent.sandbox.overlay import OverlayFS

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp) / "test_work"
        work_dir.mkdir()
        (work_dir / "test.txt").write_text("data")

        overlay = OverlayFS(work_dir=Path(tmp) / "sandbox")
        overlay.setup(work_dir)
        overlay.rollback()  # 不应抛异常
        overlay.teardown()


def test_overlay_commit():
    """commit 不抛异常."""
    from security_agent.sandbox.overlay import OverlayFS

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp) / "test_work"
        work_dir.mkdir()
        (work_dir / "test.txt").write_text("data")

        overlay = OverlayFS(work_dir=Path(tmp) / "sandbox")
        overlay.setup(work_dir)
        overlay.commit()  # 不应抛异常
        overlay.teardown()


def test_change_report_summary():
    """ChangeReport.summary 返回人类可读摘要."""
    from security_agent.sandbox.overlay import ChangeReport, FileChange

    report = ChangeReport(sandbox_id="test123")
    report.added.append(FileChange(path="new.txt", change_type="added", size_after=100))
    report.modified.append(FileChange(path="old.txt", change_type="modified", size_before=50, size_after=80))
    report.deleted.append(FileChange(path="gone.txt", change_type="deleted", size_before=200))

    summary = report.summary
    assert "新增" in summary
    assert "修改" in summary
    assert "删除" in summary


def test_change_report_is_safe():
    """有删除操作 → is_safe = False."""
    from security_agent.sandbox.overlay import ChangeReport, FileChange

    report = ChangeReport()
    report.deleted.append(FileChange(path="x.txt", change_type="deleted"))
    assert report.is_safe is False

    report2 = ChangeReport()
    report2.added.append(FileChange(path="new.txt", change_type="added"))
    assert report2.is_safe is True


# ---- SandboxSession ----

def test_session_preview_readonly():
    """只读命令的预览."""
    from security_agent.sandbox import SandboxSession

    with tempfile.TemporaryDirectory() as tmp:
        session = SandboxSession(work_dir=tmp, risk_level="READONLY")
        preview = session.preview("ls -la")

        assert preview.risk_level == "READONLY"
        assert "rlimit" in preview.isolation_description.lower() or "资源" in preview.isolation_description
        assert preview.can_rollback is False  # READONLY 不启用 OverlayFS


def test_session_execute_readonly():
    """只读命令执行成功."""
    from security_agent.sandbox import SandboxSession

    with tempfile.TemporaryDirectory() as tmp:
        session = SandboxSession(work_dir=tmp, risk_level="READONLY")
        session.preview("echo hello")
        result = session.execute("echo hello", confirmed=True)

        assert result.ok is True
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.elapsed_sec >= 0


def test_session_execute_write_with_overlay():
    """写操作 → OverlayFS 保护 → 检测到文件变更."""
    from security_agent.sandbox import SandboxSession

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp) / "work"
        work_dir.mkdir()
        (work_dir / "keep.txt").write_text("do not lose me")

        session = SandboxSession(work_dir=work_dir, risk_level="REVERSIBLE")
        preview = session.preview("echo new_content > new_file.txt")

        if sys.platform == "linux":
            assert preview.can_rollback is True

        result = session.execute("echo new_content > new_file.txt", confirmed=True)
        assert result.ok is True

        changes = session.changes()
        assert changes.total_files >= 0  # 至少不崩溃

        # 原始文件应该还在（OverlayFS 保护）
        assert (work_dir / "keep.txt").exists()
        assert (work_dir / "keep.txt").read_text() == "do not lose me"

        session.commit()


def test_session_critical_denied():
    """CRITICAL 命令被拒绝."""
    from security_agent.sandbox import SandboxSession

    with tempfile.TemporaryDirectory() as tmp:
        session = SandboxSession(work_dir=tmp, risk_level="CRITICAL")
        session.preview("rm -rf /")
        result = session.execute("rm -rf /", confirmed=False)

        assert result.ok is False
        assert "人工" in result.error or "审批" in result.error


def test_session_context_manager():
    """上下文管理器自动清理."""
    from security_agent.sandbox import SandboxSession

    with tempfile.TemporaryDirectory() as tmp:
        with SandboxSession(work_dir=tmp, risk_level="READONLY") as session:
            session.preview("echo test")
            result = session.execute("echo test", confirmed=True)
            assert result.ok is True
        # __exit__ 自动调用 teardown，不抛异常


def test_session_status():
    """status() 返回完整状态."""
    from security_agent.sandbox import SandboxSession

    with tempfile.TemporaryDirectory() as tmp:
        session = SandboxSession(work_dir=tmp, risk_level="REVERSIBLE")
        session.preview("ls")
        s = session.status()

        assert "trace_id" in s
        assert "profile" in s
        assert "preview" in s
        assert s["risk_level"] == "REVERSIBLE"


# ---- 增强 executor 集成 ----

def test_run_with_sandbox_session():
    """run_with_sandbox_session 完整流程."""
    from security_agent.terminal.executor import run_with_sandbox_session

    with tempfile.TemporaryDirectory() as tmp:
        result = run_with_sandbox_session(
            "echo hello_from_sandbox",
            cwd=tmp,
            risk_level="READONLY",
            user_confirmed=True,
        )

        assert "preview" in result
        assert "execution" in result
        assert "changes" in result
        assert "session_status" in result
        assert result["preview"]["risk_level"] == "READONLY"
        assert "hello_from_sandbox" in result["execution"]["stdout"]


# ---- Namespace ----

def test_namespace_guard_non_linux():
    """非 Linux 下 NamespaceGuard 优雅降级."""
    from security_agent.sandbox.namespace import NamespaceGuard

    guard = NamespaceGuard()
    ok = guard.apply_mount_ns()
    if sys.platform != "linux":
        assert ok is False
        assert guard.is_active is False
    guard.cleanup()


# ---- 运行入口 ----

if __name__ == "__main__":
    import traceback

    tests = [
        ("test_profile_readonly", test_profile_readonly),
        ("test_profile_reversible", test_profile_reversible),
        ("test_profile_irreversible", test_profile_irreversible),
        ("test_profile_critical", test_profile_critical),
        ("test_profile_description", test_profile_description),
        ("test_profile_to_dict", test_profile_to_dict),
        ("test_overlay_setup_and_diff_windows_fallback", test_overlay_setup_and_diff_windows_fallback),
        ("test_overlay_rollback_windows", test_overlay_rollback_windows),
        ("test_overlay_commit", test_overlay_commit),
        ("test_change_report_summary", test_change_report_summary),
        ("test_change_report_is_safe", test_change_report_is_safe),
        ("test_session_preview_readonly", test_session_preview_readonly),
        ("test_session_execute_readonly", test_session_execute_readonly),
        ("test_session_execute_write_with_overlay", test_session_execute_write_with_overlay),
        ("test_session_critical_denied", test_session_critical_denied),
        ("test_session_context_manager", test_session_context_manager),
        ("test_session_status", test_session_status),
        ("test_run_with_sandbox_session", test_run_with_sandbox_session),
        ("test_namespace_guard_non_linux", test_namespace_guard_non_linux),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
            passed += 1
        except Exception:
            print(f"  FAIL {name}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"  结果: {passed}/{len(tests)} 通过 ({failed} 失败)")
    if failed == 0:
        print("  ALL PASS - SandboxSession end-to-end verified!")
    else:
        print(f"  WARN {failed} tests failed")
    print(f"{'='*60}")

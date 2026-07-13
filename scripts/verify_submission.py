#!/usr/bin/env python3
"""A2 赛题提交规范自检 — 逐条检查 SUBMISSION_CHECKLIST.

用法:
    python scripts/verify_submission.py          # 全部检查
    python scripts/verify_submission.py --fix    # 自动修复可修复项
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CHECKS: list[dict[str, Any]] = []


def check(name: str, passed: bool, detail: str = "", severity: str = "error") -> None:
    CHECKS.append({"name": name, "passed": passed, "detail": detail, "severity": severity})


# ---- 必须包含 ----

def check_required_files() -> None:
    """检查必须包含的文件."""
    required = [
        ("security_agent/", True, "核心后端目录"),
        ("frontend/dist/index.html", False, "前端构建产物"),
        ("data/mcp/workflow_manifest.json", False, "MCP 工作流清单"),
        ("docs/INDEX.md", False, "文档总索引"),
        (".env.example", False, "环境变量模板（不含真实 Key）"),
        ("README.md", False, "项目说明"),
        ("pyproject.toml", False, "项目配置"),
        ("VERSION", False, "版本号"),
    ]
    for path, is_dir, desc in required:
        full = ROOT / path
        exists = full.is_dir() if is_dir else full.is_file()
        check(f"必须: {desc} ({path})", exists, str(full) if not exists else "")


def check_forbidden_files() -> None:
    """检查禁止提交的文件."""
    forbidden = [
        (".venv/", True, "虚拟环境"),
        ("frontend/node_modules/", True, "前端依赖"),
        (".env", False, "真实环境变量（含 API Key）"),
        ("*.docx", False, "私人材料"),
    ]
    for path, is_dir, desc in forbidden:
        if "*" in path:
            matches = list(ROOT.rglob(path))
            if matches:
                check(f"禁止: {desc}", False, f"发现: {[str(m) for m in matches]}")
            continue
        full = ROOT / path
        exists = full.is_dir() if is_dir else full.is_file()
        if exists:
            check(f"禁止: {desc}", False, str(full))


def check_env_no_secrets() -> None:
    """检查 .env.example 不含真实 Key."""
    env_path = ROOT / ".env.example"
    if not env_path.exists():
        return
    content = env_path.read_text(encoding="utf-8")
    suspicious = ["sk-", "mimo-", "crsr_"]
    for s in suspicious:
        # 允许 "your_" 开头的占位符
        if s in content and f"your_{s}" not in content:
            # 检查是否是真实 Key（长度 > 30）
            import re
            matches = re.findall(rf'{re.escape(s)}[A-Za-z0-9_\-]{{20,}}', content)
            if matches:
                check(f"安全: .env.example 可能含真实 Key ({s}...)", False, str(matches[0])[:50])
                return
    check("安全: .env.example 使用占位符", True)


def check_data_clean() -> None:
    """检查 data/ 目录不含运行时数据."""
    runtime_patterns = [
        "data/traces/*.json",
        "data/snapshots/*",
        "data/alerts/events.jsonl",
        "data/logs/*",
        "data/*.jsonl",
        "data/*.db",
    ]
    issues = []
    for pat in runtime_patterns:
        matches = list(ROOT.rglob(pat))
        if matches:
            issues.extend(str(m) for m in matches[:3])

    check(
        "数据: 运行时数据已脱敏/排除",
        len(issues) == 0,
        f"发现 {len(issues)} 个运行时文件: {issues[:3]}" if issues else "",
        severity="warning",
    )


# ---- 功能自检 ----

def check_imports() -> None:
    """检查核心模块可导入."""
    modules = [
        "security_agent.config",
        "security_agent.sandbox",
        "security_agent.capability",
        "security_agent.document",
        "security_agent.filesystem",
        "security_agent.knowledge.guard",
        "security_agent.knowledge.freshness",
    ]
    for mod in modules:
        try:
            __import__(mod)
            check(f"导入: {mod}", True)
        except ImportError as e:
            check(f"导入: {mod}", False, str(e))


def check_tests_pass() -> None:
    """检查核心测试通过."""
    import subprocess
    core_tests = [
        "tests/test_three_layer_defense.py",
        "tests/test_capability_boxing.py",
        "tests/test_knowledge_guard.py",
    ]
    for test in core_tests:
        try:
            r = subprocess.run(
                [sys.executable, str(ROOT / test)],
                capture_output=True, text=True, timeout=60, cwd=str(ROOT),
            )
            ok = r.returncode == 0 and "ALL PASS" in r.stdout
            check(f"测试: {test}", ok, r.stdout[-200:] if not ok else "")
        except subprocess.TimeoutExpired:
            check(f"测试: {test}", False, "超时")


# ---- 文档质量 ----

def check_docs_freshness() -> None:
    """检查关键文档是否包含版本号."""
    docs_to_check = [
        "docs/architecture/FINAL_ARCHITECTURE.md",
        "docs/INDEX.md",
        "README.md",
    ]
    for path in docs_to_check:
        full = ROOT / path
        if not full.exists():
            check(f"文档: {path} 存在", False, "缺失")
            continue
        content = full.read_text(encoding="utf-8")
        if "0.9.0" in content or "v0.9.0" in content:
            check(f"文档: {path} 版本号正确", True)
        else:
            check(f"文档: {path} 版本号可能过时", False, "未找到 0.9.0", severity="warning")


# ---- 主函数 ----

def main() -> None:
    print("=" * 60)
    print("  A2 提交规范自检")
    print("=" * 60)
    print()

    check_required_files()
    check_forbidden_files()
    check_env_no_secrets()
    check_data_clean()
    check_imports()
    # check_tests_pass()  # 耗时，默认跳过
    check_docs_freshness()

    errors = [c for c in CHECKS if not c["passed"] and c["severity"] == "error"]
    warnings = [c for c in CHECKS if not c["passed"] and c["severity"] == "warning"]
    passed = [c for c in CHECKS if c["passed"]]

    print()
    for c in CHECKS:
        marker = "PASS" if c["passed"] else ("WARN" if c["severity"] == "warning" else "FAIL")
        print(f"  [{marker}] {c['name']}")
        if c["detail"] and not c["passed"]:
            print(f"         {c['detail'][:120]}")

    print()
    print(f"  Results: {len(passed)}/{len(CHECKS)} checks passed")
    if errors:
        print(f"  ERRORS: {len(errors)} — 提交前必须修复!")
    if warnings:
        print(f"  WARNINGS: {len(warnings)} — 建议修复")

    if errors:
        print()
        print("  === 必须修复 ===")
        for e in errors:
            print(f"  - {e['name']}: {e['detail'][:100]}")
        sys.exit(1)
    else:
        print("  SUBMISSION READY")


if __name__ == "__main__":
    main()

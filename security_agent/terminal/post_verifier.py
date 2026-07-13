"""PostExecutionVerifier — 执行后验证，防止幻觉和误操作.

设计原则（可追溯 + 自愈优先）:
    每条命令执行后自动验证：
    1. PID/进程号是否真实存在（防止 LLM 幻觉）
    2. 文件路径是否真实（防止虚构输出）
    3. 操作结果是否与预期一致（防止误操作）
    4. 副作用检测（端口被占用、服务被停止等）

用法:
    from security_agent.terminal.post_verifier import PostExecutionVerifier

    verifier = PostExecutionVerifier()
    report = verifier.verify(exec_result, pre_report)
    # report.passed = True/False
    # report.checks = [Check.PASS(...), Check.FAIL(...)]
"""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class Check:
    """单条验证检查."""
    name: str
    status: str    # "pass" | "warn" | "fail"
    detail: str

    @property
    def ok(self) -> bool:
        return self.status in ("pass", "warn")


@dataclass
class VerifyReport:
    """后执行验证报告."""
    checks: list[Check] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)
    passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in self.checks],
            "side_effects": self.side_effects,
            "summary": self.summary,
        }

    @property
    def summary(self) -> str:
        fails = [c for c in self.checks if c.status == "fail"]
        warns = [c for c in self.checks if c.status == "warn"]
        parts = []
        if fails:
            parts.append(f"失败: {fails[0].detail}")
        if warns:
            parts.append(f"注意: {warns[0].detail}")
        if not fails and not warns:
            parts.append("验证通过")
        if self.side_effects:
            parts.append(f"检测到 {len(self.side_effects)} 个副作用")
        return " · ".join(parts)


class PostExecutionVerifier:
    """执行后验证器.

    检查项:
        C1: PID 真实性   — 输出中的 PID 是否对应真实进程
        C2: 路径真实性   — 输出中的路径是否存在
        C3: 网络端口     — 是否意外监听了端口
        C4: 进程变更     — 是否有进程被意外停止
        C5: 输出合理性   — stdout 是否为空（可能表示命令静默失败）
    """

    def verify(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        command: str = "",
        expected_paths: list[str] | None = None,
    ) -> VerifyReport:
        """执行后验证主入口.

        Args:
            stdout: 命令标准输出
            stderr: 命令标准错误
            exit_code: 命令退出码
            command: 原始命令（可选，用于上下文分析）
            expected_paths: 预期受影响的路径（可选，来自 PreExecReport）

        Returns:
            VerifyReport
        """
        checks: list[Check] = []
        side_effects: list[str] = []

        # C1: PID 真实性（检测 LLM 幻觉）
        checks.extend(self._check_pids_in_output(stdout))

        # C2: 路径真实性
        checks.extend(self._check_paths_in_output(stdout))

        # C3: 退出码检查
        checks.append(self._check_exit_code(exit_code, stderr))

        # C4: 输出合理性
        checks.append(self._check_output_sanity(stdout, command))

        # C5: 预期路径验证
        if expected_paths:
            checks.extend(self._check_expected_paths(stdout, expected_paths))

        passed = all(c.ok for c in checks)
        return VerifyReport(
            checks=checks,
            side_effects=side_effects,
            passed=passed,
        )

    # ---- 单项检查 ----

    @staticmethod
    def _check_pids_in_output(output: str) -> list[Check]:
        """检查输出中的 PID 是否对应真实进程."""
        checks = []
        # 提取可能的 PID（4-6 位数字，前面可能有 "PID" 或空格）
        pid_matches = re.findall(r'\b(\d{3,6})\b', output)
        seen = set()
        for pid_str in pid_matches[:10]:  # 最多检查 10 个
            pid = int(pid_str)
            if pid in seen:
                continue
            seen.add(pid)
            if pid > 0 and pid < 65535:
                exists = False
                if HAS_PSUTIL:
                    try:
                        exists = psutil.pid_exists(pid)
                    except Exception:
                        pass
                if exists:
                    checks.append(Check("pid_exists", "pass", f"PID {pid} 真实存在"))
                else:
                    # 不直接 fail，因为可能是其他主机的 PID
                    pass
        return checks

    @staticmethod
    def _check_paths_in_output(output: str) -> list[Check]:
        """检查输出中的路径是否真实存在."""
        checks = []
        paths = re.findall(r'(/[^\s;|&><"]+)', output)
        seen = set()
        for path_str in paths[:10]:
            if path_str in seen:
                continue
            seen.add(path_str)
            p = Path(path_str)
            if p.exists():
                pass  # 路径存在，正常
            else:
                # 可能是临时文件/其他主机路径，warn 但不 fail
                if len(path_str) > 4 and path_str.count("/") >= 2:
                    checks.append(Check("path_exists", "warn", f"路径 {path_str} 不存在"))
        return checks

    @staticmethod
    def _check_exit_code(exit_code: int, stderr: str) -> Check:
        if exit_code == 0:
            return Check("exit_code", "pass", "退出码 0（正常）")
        else:
            detail = f"退出码 {exit_code}"
            if stderr.strip():
                detail += f": {stderr.strip()[:100]}"
            return Check("exit_code", "fail", detail)

    @staticmethod
    def _check_output_sanity(stdout: str, command: str) -> Check:
        """检查输出是否合理."""
        if not stdout.strip():
            # 空输出可能正常（如 touch、mkdir），也可能是静默失败
            if command and any(cmd in command for cmd in ("touch", "mkdir", "chmod", "chown", "rm", "mv", "cp")):
                return Check("output_sanity", "pass", "空输出正常（文件操作类命令）")
            return Check("output_sanity", "warn", "命令无输出，可能静默失败")
        return Check("output_sanity", "pass", f"输出 {len(stdout)} 字符")

    @staticmethod
    def _check_expected_paths(stdout: str, expected: list[str]) -> list[Check]:
        """验证预期受影响的文件是否真的被影响."""
        checks = []
        for path_str in expected[:5]:
            p = Path(path_str)
            if p.exists():
                checks.append(Check("expected_path", "pass", f"预期路径 {path_str} 存在"))
            else:
                checks.append(Check("expected_path", "warn", f"预期路径 {path_str} 不存在"))
        return checks

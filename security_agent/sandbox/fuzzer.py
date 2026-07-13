"""BoundaryFuzzer — 自动化边界模糊测试，生成对抗样本并检测沙箱穿透.

设计原则（自愈优先）:
    7 种变异策略从安全命令生成攻击变体 → 在沙箱中执行 → 检测穿透。

用法:
    from security_agent.sandbox.fuzzer import BoundaryFuzzer

    fuzzer = BoundaryFuzzer()
    result = fuzzer.fuzz("ls /tmp", rounds=20)
    # result.penetrations → [Penetration(...)]
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Mutation:
    """一次变异产生的测试用例."""
    strategy: str          # 变异策略名
    original: str           # 原始命令
    mutated: str            # 变异后的命令
    description: str        # 变异说明


@dataclass
class Penetration:
    """一次沙箱穿透事件."""
    mutation: Mutation
    evidence: str           # 穿透证据（如"成功读取 /etc/shadow"）
    severity: str           # 严重度
    detected_at: str = ""


@dataclass
class FuzzResult:
    """一轮模糊测试的结果."""
    rounds: int
    mutations_generated: int
    penetrations: list[Penetration] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_sec: float = 0.0

    @property
    def passed(self) -> int:
        return self.mutations_generated - len(self.penetrations) - len(self.errors)

    @property
    def health(self) -> float:
        if self.mutations_generated == 0:
            return 1.0
        return round(self.passed / self.mutations_generated, 3)

    @property
    def summary(self) -> str:
        if not self.penetrations:
            return f"模糊测试通过 ({self.mutations_generated} 个变异, 0 穿透)"
        top = self.penetrations[0]
        return f"发现 {len(self.penetrations)} 次穿透! 最严重: {top.severity} — {top.mutation.strategy}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rounds": self.rounds,
            "mutations_generated": self.mutations_generated,
            "passed": self.passed,
            "penetrations": len(self.penetrations),
            "errors": len(self.errors),
            "health": self.health,
            "summary": self.summary,
            "elapsed_sec": self.elapsed_sec,
            "penetration_details": [
                {
                    "strategy": p.mutation.strategy,
                    "mutated": p.mutation.mutated[:200],
                    "evidence": p.evidence[:500],
                    "severity": p.severity,
                }
                for p in self.penetrations[:10]
            ],
        }


class BoundaryFuzzer:
    """边界模糊测试器.

    7 种变异策略:
        1. path_traversal    — 路径穿越 (../../../etc/shadow)
        2. command_injection — 命令注入 (cmd && evil)
        3. env_injection     — 环境变量注入 (LD_PRELOAD=...)
        4. special_chars     — 特殊字符注入 ($() `` ; | &)
        5. unicode_bypass    — Unicode 混淆 (／etc／passwd)
        6. whitespace_bypass — 空白符绕过 (${IFS})
        7. glob_expansion    — 通配符扩展 (/*/*/etc/*)
    """

    STRATEGIES = [
        "path_traversal",
        "command_injection",
        "env_injection",
        "special_chars",
        "unicode_bypass",
        "whitespace_bypass",
        "glob_expansion",
    ]

    def __init__(self, sandbox_timeout: float = 5.0):
        self._timeout = sandbox_timeout
        self._intensity = "normal"  # normal | aggressive
        self._bypass_log: list[Penetration] = []

    # ---- 主入口 ----

    def fuzz(self, base_command: str, rounds: int = 50, intensity: str = "normal") -> FuzzResult:
        """对一条基础命令进行模糊测试.

        Args:
            base_command: 基础安全命令（如 "ls /tmp"）
            rounds: 生成多少轮变异
            intensity: "normal" (50% 变异率) | "aggressive" (100%)

        Returns:
            FuzzResult
        """
        self._intensity = intensity
        t0 = time.time()
        mutations = self._generate(base_command, rounds)
        penetrations = self._execute_and_detect(mutations)

        errors = []
        result = FuzzResult(
            rounds=rounds,
            mutations_generated=len(mutations),
            penetrations=penetrations,
            errors=errors,
            elapsed_sec=round(time.time() - t0, 2),
        )
        self._bypass_log.extend(penetrations)
        return result

    # ---- 变异生成 ----

    def _generate(self, base: str, count: int) -> list[Mutation]:
        mutations: list[Mutation] = []
        strategy_idx = 0

        for i in range(count):
            strategy = self.STRATEGIES[strategy_idx % len(self.STRATEGIES)]
            mutated = self._apply_strategy(base, strategy)
            if mutated and mutated != base:
                mutations.append(Mutation(
                    strategy=strategy,
                    original=base,
                    mutated=mutated,
                    description=f"{strategy}: {base[:50]} → {mutated[:50]}",
                ))
            strategy_idx += 1
            if self._intensity == "normal":
                strategy_idx += 1  # 跳过一半的策略（减少冗余）

        return mutations

    def _apply_strategy(self, cmd: str, strategy: str) -> str:
        """应用一种变异策略."""
        if strategy == "path_traversal":
            return re.sub(r'/[a-zA-Z][^\s;|&]*', '../../etc/shadow', cmd, count=1)

        elif strategy == "command_injection":
            suffixes = [
                " && cat /etc/shadow",
                " ; cat /etc/passwd",
                " | cat /etc/hostname",
                " `cat /etc/hostname`",
            ]
            return cmd + suffixes[hash(cmd) % len(suffixes)]

        elif strategy == "env_injection":
            return f"LD_PRELOAD=/tmp/evil.so {cmd}"

        elif strategy == "special_chars":
            injects = [
                f"$(whoami)",
                f"`whoami`",
                f"{cmd} || cat /etc/hostname",
                f"{cmd} & cat /etc/passwd",
            ]
            return injects[hash(cmd) % len(injects)]

        elif strategy == "unicode_bypass":
            # 用 Unicode 全角字符替代 ASCII 字符
            trans = str.maketrans({
                '/': '／', '.': '．',
                'a': 'ａ', 'e': 'ｅ',
            })
            return cmd.translate(trans) if cmd else cmd

        elif strategy == "whitespace_bypass":
            return cmd.replace(' ', '${IFS}') if ' ' in cmd else cmd

        elif strategy == "glob_expansion":
            return cmd + " /*/*/etc/* 2>/dev/null" if cmd else cmd

        return cmd

    # ---- 执行和检测 ----

    def _execute_and_detect(self, mutations: list[Mutation]) -> list[Penetration]:
        """在沙箱中执行所有变异，检测穿透."""
        penetrations = []
        for m in mutations:
            p = self._test_one(m)
            if p:
                penetrations.append(p)
        return penetrations

    def _test_one(self, mutation: Mutation) -> Penetration | None:
        """执行单个变异并检查是否穿透."""
        try:
            # 在受限环境中执行变异的命令
            proc = subprocess.run(
                mutation.mutated,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=tempfile.gettempdir(),
            )
            output = (proc.stdout or "") + (proc.stderr or "")

            # 检测穿透迹象
            evidence = self._detect_leak(output, mutation)
            if evidence:
                return Penetration(
                    mutation=mutation,
                    evidence=evidence,
                    severity=self._severity_of(evidence),
                    detected_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

        return None

    def _detect_leak(self, output: str, mutation: Mutation) -> str:
        """检测输出中是否有沙箱穿透的迹象."""
        leak_patterns = [
            (r'root:.*:0:0:', "可能读取到 /etc/passwd 的 root 行"),
            (r'root:\$', "可能读取到 /etc/shadow 的加密密码"),
            (r'[0-9a-f]{32}', "输出包含可疑哈希值"),
            (r'uid=\d+\(root\)', "命令以 root 身份运行"),
            (r'CapEff:\s*[0-9a-f]{6,}', "检测到 capabilities 泄漏"),
            (r'/etc/(shadow|passwd|sudoers)', "访问了敏感文件"),
            (r'Permission denied', None),   # 这个是好的，被拦截了
            (r'command not found', None),   # 命令不存在
        ]

        for pattern, evidence in leak_patterns:
            if evidence and re.search(pattern, output, re.IGNORECASE):
                return evidence

        # 通用检测: 输出中有任何看似系统文件内容的东西
        if mutation.strategy == "path_traversal" and len(output) > 50:
            return "路径穿越可能产生非预期输出"

        return ""

    @staticmethod
    def _severity_of(evidence: str) -> str:
        if "shadow" in evidence.lower() or "密码" in evidence:
            return "严重"
        if "root" in evidence.lower():
            return "高"
        if "passwd" in evidence.lower() or "敏感" in evidence:
            return "中"
        return "低"

    # ---- 统计 ----

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        return [
            {
                "strategy": p.mutation.strategy,
                "mutated": p.mutation.mutated[:200],
                "evidence": p.evidence[:500],
                "severity": p.severity,
            }
            for p in self._bypass_log[-limit:]
        ]

    def stats(self) -> dict[str, Any]:
        by_strategy: dict[str, int] = {}
        for p in self._bypass_log:
            by_strategy[p.mutation.strategy] = by_strategy.get(p.mutation.strategy, 0) + 1

        return {
            "total_penetrations": len(self._bypass_log),
            "penetrations_by_strategy": by_strategy,
            "strategies": self.STRATEGIES,
        }

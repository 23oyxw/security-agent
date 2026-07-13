"""ExecutionLearner — 从每次终端操作中学习，持续优化.

设计原则（自愈优先 + 渐进式）:
    1. 记录成功命令的模式 → 下次秒级建议
    2. 记录失败命令的原因 → 调整风险评估
    3. 长期分析 → 识别高风险操作模式

存储:
    数据持久化到 data/execution_learner.jsonl
    启动时加载，执行后追加。

用法:
    from security_agent.terminal.learner import ExecutionLearner

    learner = ExecutionLearner()
    learner.learn(intent="清理日志", command="find /var/log -name '*.log' -mtime +30 -delete",
                  ok=True, cmd_type="delete", risk_score=0.5)
    # 下次用户说"清理日志"时，秒出建议
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from security_agent import config

# 数据文件
_LEARNER_PATH = config.DATA_DIR / "execution_learner.jsonl"


class ExecutionLearner:
    """终端执行学习器.

    三个功能:
        1. learn()     — 记录一次执行，更新模型
        2. suggest()   — 根据意图推荐命令
        3. stats()     — 查看学习统计
    """

    def __init__(self):
        self._intent_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._command_success: dict[str, dict[str, int]] = defaultdict(
            lambda: {"success": 0, "failure": 0}
        )
        self._type_risk: dict[str, dict[str, float]] = defaultdict(
            lambda: {"total": 0, "failures": 0}
        )
        self._load()

    # ---- 学习 ----

    def learn(
        self,
        *,
        intent: str = "",
        command: str,
        ok: bool,
        cmd_type: str = "",
        risk_score: float = 0.0,
        trace_id: str = "",
    ) -> None:
        """记录一次执行并更新模型.

        Args:
            intent: 用户意图（自然语言，可为空）
            command: 执行的命令
            ok: 是否成功
            cmd_type: 命令类型（observe/modify/delete/network/privilege）
            risk_score: 预判风险分
            trace_id: 追踪 ID
        """
        entry = {
            "intent": intent,
            "command": command,
            "ok": ok,
            "type": cmd_type,
            "risk_score": risk_score,
            "trace_id": trace_id,
            "learned_at": time.time(),
        }

        # 内存更新
        if intent:
            self._intent_map[intent].append(entry)
            # 只保留最近的 20 条同意图记录
            if len(self._intent_map[intent]) > 20:
                self._intent_map[intent] = self._intent_map[intent][-20:]

        cmd_key = command.split()[0] if command else "unknown"
        if ok:
            self._command_success[cmd_key]["success"] += 1
        else:
            self._command_success[cmd_key]["failure"] += 1

        if cmd_type:
            self._type_risk[cmd_type]["total"] += 1
            if not ok:
                self._type_risk[cmd_type]["failures"] += 1

        # 持久化
        self._save(entry)

    # ---- 建议 ----

    def suggest(self, intent: str, max_results: int = 3) -> list[dict[str, Any]]:
        """根据意图推荐命令.

        Args:
            intent: 用户意图（自然语言）
            max_results: 最多返回几条建议

        Returns:
            [{"command": str, "success_rate": float, "last_used": float, "count": int}]
        """
        if not intent:
            return []

        # 模糊匹配（简单的关键词重叠）
        best_key = None
        best_score = 0
        intent_lower = intent.lower()
        for key in self._intent_map:
            key_set = set(key)
            intent_set = set(intent_lower)
            overlap = len(key_set & intent_set) / max(len(key_set), 1)
            if overlap > best_score:
                best_score = overlap
                best_key = key

        if not best_key or best_score < 0.2:
            return []

        # 聚合同意图下的命令
        entries = self._intent_map[best_key]
        cmd_agg: dict[str, dict[str, Any]] = {}
        for e in entries:
            cmd = e["command"]
            if cmd not in cmd_agg:
                cmd_agg[cmd] = {"command": cmd, "success": 0, "failure": 0, "last_used": 0.0, "type": e["type"]}
            if e["ok"]:
                cmd_agg[cmd]["success"] += 1
            else:
                cmd_agg[cmd]["failure"] += 1
            cmd_agg[cmd]["last_used"] = max(cmd_agg[cmd]["last_used"], e["learned_at"])

        # 按成功率排序
        ranked = []
        for cmd, agg in cmd_agg.items():
            total = agg["success"] + agg["failure"]
            rate = agg["success"] / total if total > 0 else 1.0
            ranked.append({
                "command": cmd,
                "success_rate": round(rate, 3),
                "count": total,
                "last_used_ago_sec": round(time.time() - agg["last_used"], 0),
                "type": agg["type"],
            })

        ranked.sort(key=lambda x: (-x["success_rate"], -x["count"]))
        return ranked[:max_results]

    # ---- 统计 ----

    def stats(self) -> dict[str, Any]:
        """学习统计."""
        total = sum(v["success"] + v["failure"] for v in self._command_success.values())
        total_ok = sum(v["success"] for v in self._command_success.values())

        # 计算每种命令类型的实际风险（失败率）
        type_risk = {}
        for t, data in self._type_risk.items():
            if data["total"] > 0:
                type_risk[t] = {
                    "total": data["total"],
                    "failure_rate": round(data["failures"] / data["total"], 3),
                }

        return {
            "total_executions": total,
            "overall_success_rate": round(total_ok / total, 3) if total > 0 else None,
            "intents_learned": len(self._intent_map),
            "commands_tracked": len(self._command_success),
            "type_risk_actual": type_risk,
        }

    # ---- 持久化 ----

    def _save(self, entry: dict[str, Any]) -> None:
        try:
            _LEARNER_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_LEARNER_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load(self) -> None:
        if not _LEARNER_PATH.exists():
            return
        try:
            for line in _LEARNER_PATH.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    self.learn(
                        intent=entry.get("intent", ""),
                        command=entry.get("command", ""),
                        ok=entry.get("ok", False),
                        cmd_type=entry.get("type", ""),
                        risk_score=entry.get("risk_score", 0.0),
                        trace_id=entry.get("trace_id", ""),
                    )
                except (json.JSONDecodeError, KeyError):
                    continue
        except OSError:
            pass


# 全局单例
_learner: ExecutionLearner | None = None


def get_learner() -> ExecutionLearner:
    global _learner
    if _learner is None:
        _learner = ExecutionLearner()
    return _learner

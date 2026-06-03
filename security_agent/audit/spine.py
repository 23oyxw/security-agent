"""事件脊柱（Incident Spine）— 统一 trace_id、审计、推理追溯与请求预算."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Generator

from security_agent.audit import log as audit
from security_agent.audit.reasoning_trace import ReasoningTrace, ThoughtType, TraceStatus
from security_agent.audit.trace import TraceContext
from security_agent.resilience.budget import RequestBudget, request_budget
from security_agent.resilience.degradation import DegradationLevel


def new_trace_id() -> str:
    return f"trace-{uuid.uuid4().hex[:12]}"


class IncidentSpine:
    """一次用户请求的脊柱：TraceContext + ReasoningTrace + RequestBudget."""

    def __init__(
        self,
        user_message: str,
        *,
        trace_id: str = "",
        session_id: str = "",
        user: str = "",
        budget_sec: float = 120.0,
    ):
        self.trace_id = trace_id or new_trace_id()
        self.user_message = user_message
        self.degradation_level = DegradationLevel.S0_FULL.value
        self.budget = RequestBudget(total_sec=budget_sec, trace_id=self.trace_id)
        self.trace_ctx = TraceContext(
            trace_id=self.trace_id,
            user_message=user_message,
            user=user,
            metadata={"spine": True, "session_id": session_id},
        )
        self.reasoning = ReasoningTrace(
            user_message,
            session_id=session_id,
            strategy="react",
            trace_id=self.trace_id,
        )

    def stage(self, name: str, detail: dict[str, Any] | None = None) -> None:
        detail = dict(detail or {})
        detail.setdefault("degradation_level", self.degradation_level)
        self.trace_ctx.stage(name, detail)
        self.reasoning.record_thought(
            ThoughtType.OBSERVATION,
            content=f"[{name}] {str(detail)[:500]}",
            metadata={"stage": name},
        )

    def set_degradation(self, level: DegradationLevel | str, reason: str = "") -> None:
        self.degradation_level = level.value if isinstance(level, DegradationLevel) else str(level)
        self.stage(
            "degradation",
            {"level": self.degradation_level, "reason": reason[:300]},
        )
        audit.append_audit(
            "degradation",
            {"trace_id": self.trace_id, "level": self.degradation_level, "reason": reason},
            level="warning",
        )

    def record_llm_meta(self, meta: dict[str, Any]) -> None:
        if meta.get("fallback_used"):
            self.set_degradation(DegradationLevel.S1_MODEL_FB, "model_fallback")
        self.stage("inference_decision", {"llm": meta})

    def post_verify(self, detail: dict[str, Any]) -> bool:
        ok = detail.get("ok", detail.get("exit_code", 1) == 0)
        self.stage("post_verify", {**detail, "verified": ok})
        if not ok:
            self.reasoning.update_status(TraceStatus.VERIFYING)
            self.reasoning.record_error(
                error_type="PostVerifyFailed",
                error_message=detail.get("message", "post_verify failed"),
            )
        return bool(ok)

    def finish_ok(self) -> None:
        self.reasoning.update_status(TraceStatus.COMPLETED)


@contextmanager
def incident_spine(
    user_message: str,
    **kwargs: Any,
) -> Generator[IncidentSpine, None, None]:
    spine = IncidentSpine(user_message, **kwargs)
    with request_budget(spine.budget):
        audit.append_audit(
            "incident_spine_begin",
            {"trace_id": spine.trace_id, "user_message": user_message[:200]},
        )
        spine.trace_ctx.__enter__()
        spine.reasoning.__enter__()
        try:
            yield spine
            spine.finish_ok()
            status = "completed"
            if spine.degradation_level != DegradationLevel.S0_FULL.value:
                status = f"completed_{spine.degradation_level}"
            spine.trace_ctx.complete_trace(status)
        except Exception as exc:
            spine.trace_ctx.complete_trace("failed")
            spine.reasoning.record_error(
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise
        finally:
            spine.trace_ctx.__exit__(None, None, None)
            spine.reasoning.__exit__(None, None, None)
            audit.append_audit(
                "incident_spine_end",
                {
                    "trace_id": spine.trace_id,
                    "degradation_level": spine.degradation_level,
                    "budget": spine.budget.to_dict(),
                },
            )


def _skill_flow_subtrace_id(sqlite_trace: dict[str, Any] | None, outer_trace_id: str) -> str:
    """L2 runner 在 audit 里用的短 trace_id（与 incident spine 的 trace-xxx 不同）."""
    if not sqlite_trace:
        return ""
    for stage in sqlite_trace.get("stages") or []:
        if (stage.get("name") or stage.get("stage")) != "skill_flow_end":
            continue
        data = stage.get("data") or {}
        if not isinstance(data, dict):
            continue
        inner = str(data.get("trace_id") or "").strip()
        if inner and inner != outer_trace_id:
            return inner
    return ""


def export_incident_bundle(trace_id: str) -> dict[str, Any]:
    """导出法庭卷宗：SQLite 阶段 + audit 片段 + reasoning jsonl."""
    from security_agent import config
    from security_agent.audit.log import read_audit_tail
    from security_agent.audit.reasoning_trace import ReasoningTrace
    from security_agent.resilience.circuit import list_circuit_states
    from security_agent.storage.trace_storage import get_trace_storage

    bundle: dict[str, Any] = {
        "trace_id": trace_id,
        "sqlite_trace": None,
        "audit_events": [],
        "reasoning_report": None,
        "circuits": list_circuit_states(),
    }

    try:
        bundle["sqlite_trace"] = get_trace_storage().get_trace(trace_id)
    except Exception as exc:
        bundle["sqlite_error"] = str(exc)

    sub_tid = _skill_flow_subtrace_id(bundle.get("sqlite_trace"), trace_id)
    seen: set[str] = set()

    def _append(entry: dict[str, Any]) -> None:
        key = f"{entry.get('ts')}|{entry.get('action')}|{str(entry.get('detail'))[:80]}"
        if key in seen:
            return
        seen.add(key)
        bundle["audit_events"].append(entry)

    for entry in read_audit_tail(limit=1500):
        detail = entry.get("detail") or {}
        tid = detail.get("trace_id") if isinstance(detail, dict) else ""
        if tid == trace_id or trace_id in str(entry):
            _append(entry)
        if len(bundle["audit_events"]) >= 80:
            break

    if sub_tid:
        for entry in read_audit_tail(limit=1500):
            if entry.get("action") not in ("skill_flow_start", "skill_flow_end"):
                continue
            detail = entry.get("detail") or {}
            if isinstance(detail, dict) and detail.get("trace_id") == sub_tid:
                _append(entry)

    trace_dir = config.DATA_DIR / "traces"
    if trace_dir.is_dir():
        for fp in sorted(trace_dir.glob("*.jsonl"), reverse=True):
            recs = ReasoningTrace.from_jsonl(fp, trace_id=trace_id)
            if recs:
                bundle["reasoning_report"] = recs[-1]
                break

    return bundle

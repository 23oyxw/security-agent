"""Inspection runner: execute cases, assert, report."""
from __future__ import annotations
import json, subprocess, time, uuid
from pathlib import Path
from typing import Any
from security_agent import config
from security_agent.inspection.assert_rules import evaluate_assert
from security_agent.inspection.suites import load_suite, list_suite_ids
from security_agent.timeutil import now_iso

REPORTS_DIR = config.DATA_DIR / "inspection" / "reports"
MAX_RETRIES = 2
CMD_TIMEOUT = 30

def list_suites() -> list[dict[str, str]]:
    return list_suite_ids()

def _run_command(cmd: str) -> dict[str, Any]:
    if config.IS_WINDOWS:
        return {"ok": False, "stdout": "", "stderr": "skip: non-linux", "exit_code": -1, "skipped": True}
    last_err = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                timeout=CMD_TIMEOUT, encoding="utf-8", errors="replace")
            return {"ok": proc.returncode == 0, "stdout": proc.stdout or "", "stderr": proc.stderr or "",
                "exit_code": proc.returncode, "attempt": attempt + 1, "skipped": False}
        except subprocess.TimeoutExpired:
            last_err = "timeout"
        except OSError as e:
            last_err = str(e)
    return {"ok": False, "stdout": "", "stderr": last_err or "exec failed", "exit_code": -1, "offline": True, "skipped": False}

def _grade_rank(grade: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(grade, 9)

async def run_suite(suite_id: str, *, trace_id: str | None = None, push_webhook: bool = True) -> dict[str, Any]:
    suite = load_suite(suite_id)
    run_id = str(uuid.uuid4())[:12]
    t0 = time.perf_counter()
    cases_out: list[dict[str, Any]] = []
    failed = skipped = 0
    for case in suite.get("cases") or []:
        cid = case.get("id", "case")
        exec_res = _run_command(str(case.get("command", "true")))
        if exec_res.get("skipped"):
            skipped += 1
            cases_out.append({"id": cid, "title": case.get("title", cid), "status": "skipped",
                "grade": case.get("grade", "P3"), "detail": exec_res.get("stderr", "")})
            continue
        passed, reason = evaluate_assert(exec_res.get("stdout", ""), case.get("assert"))
        status = "pass" if passed else "fail"
        if not passed:
            failed += 1
        cases_out.append({"id": cid, "title": case.get("title", cid), "category": case.get("category", ""),
            "status": status, "grade": case.get("grade", "P3"), "assert_reason": reason,
            "command": str(case.get("command", ""))[:200], "stdout_preview": (exec_res.get("stdout") or "")[:500],
            "exit_code": exec_res.get("exit_code"), "offline": exec_res.get("offline", False)})
    total = len(cases_out)
    passed_n = sum(1 for c in cases_out if c["status"] == "pass")
    worst = min((_grade_rank(c.get("grade", "P3")) for c in cases_out if c["status"] == "fail"), default=9)
    worst_grade = {0: "P0", 1: "P1", 2: "P2", 3: "P3"}.get(worst, "P3") if failed else "OK"
    report = {"run_id": run_id, "suite_id": suite_id, "suite_name": suite.get("name", suite_id),
        "trace_id": trace_id, "ts": now_iso(), "read_only": bool(suite.get("read_only", True)),
        "summary": {"total": total, "passed": passed_n, "failed": failed, "skipped": skipped,
            "pass_rate": round(passed_n / total * 100, 1) if total else 0, "worst_grade": worst_grade, "ok": failed == 0},
        "cases": cases_out, "elapsed_ms": round((time.perf_counter() - t0) * 1000), "engine": "huace-inspection-v1"}
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{suite_id}_{run_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORTS_DIR / f"{suite_id}_latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(path)
    if push_webhook and failed > 0 and worst_grade in ("P0", "P1"):
        try:
            from security_agent.notify.webhook import push_inspection_alert
            push_inspection_alert(report)
        except Exception:
            pass
    try:
        from security_agent.inspection.risk_window import record_inspection_sample
        record_inspection_sample(failed, worst_grade)
    except Exception:
        pass
    return report

def get_latest_report(suite_id: str) -> dict[str, Any] | None:
    path = REPORTS_DIR / f"{suite_id}_latest.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

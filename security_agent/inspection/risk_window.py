"""L5 risk window via sliding stats (no statsmodels)."""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime
from typing import Any
from security_agent import config

SAMPLES_PATH = config.DATA_DIR / "monitor" / "inspection_ts.jsonl"

def record_inspection_sample(failed_count: int, worst_grade: str) -> None:
    SAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "hour": datetime.now().hour,
        "failed": failed_count, "worst_grade": worst_grade}
    with SAMPLES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def predict_risk_window(last_n: int = 48) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if SAMPLES_PATH.is_file():
        for line in SAMPLES_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    rows = rows[-last_n:]
    if not rows:
        return {"mode": "sliding_window", "samples": 0,
            "message": "no samples yet; run POST /api/inspection/run first", "high_risk_hours": [], "forecast": ""}
    hour_fail = Counter()
    total_failed = 0
    for r in rows:
        hour_fail[int(r.get("hour", 0))] += int(r.get("failed", 0))
        total_failed += int(r.get("failed", 0))
    top_hours = [h for h, _ in hour_fail.most_common(3)]
    recent_fail = sum(int(r.get("failed", 0)) for r in rows[-6:])
    avg_fail = total_failed / len(rows)
    trend = "up" if recent_fail > avg_fail * 1.5 else ("stable" if recent_fail <= avg_fail else "volatile")
    peak_hour = hour_fail.most_common(1)[0][0] if hour_fail else datetime.now().hour
    return {"mode": "sliding_window", "samples": len(rows), "total_failed": total_failed,
        "avg_failed_per_run": round(avg_fail, 2), "trend": trend, "high_risk_hours": top_hours,
        "peak_risk_hour": peak_hour,
        "forecast": f"peak risk near hour {peak_hour:02d}:00; run kylin_baseline before that window",
        "recommendations": ["run kylin_baseline", "review P0/P1 in /alerts", "use repair + auto-retest"]}

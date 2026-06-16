"""Pluggable webhook alerts (default off, no Feishu dependency)."""
from __future__ import annotations
import time
from typing import Any
from security_agent import config

_CONFIG_PATH = config.PROJECT_ROOT / "configs" / "notify_channels.yaml"
_last_push: dict[str, float] = {}

def _load_config() -> dict[str, Any]:
    if not _CONFIG_PATH.is_file():
        return {"enabled": False, "channels": []}
    import yaml
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"enabled": False, "channels": []}

def _grade_ok(grade: str, min_grade: str) -> bool:
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "OK": 9}
    return order.get(grade, 9) <= order.get(min_grade, 1)

def _build_payload(template: str, title: str, body: str) -> dict[str, Any]:
    if template == "wecom_text":
        return {"msgtype": "text", "text": {"content": f"{title}\n{body}"}}
    if template == "feishu_text":
        return {"msg_type": "text", "content": {"text": f"{title}\n{body}"}}
    return {"title": title, "body": body, "source": "security-agent"}

def push_webhook(title: str, body: str, *, grade: str = "P1") -> dict[str, Any]:
    cfg = _load_config()
    if not cfg.get("enabled"):
        return {"ok": False, "skipped": True, "reason": "webhook disabled"}
    if not _grade_ok(grade, str(cfg.get("min_grade") or "P1")):
        return {"ok": False, "skipped": True, "reason": "grade below threshold"}
    dedupe = int(cfg.get("dedupe_seconds") or 300)
    key = f"{grade}:{title[:40]}"
    now = time.time()
    if now - _last_push.get(key, 0) < dedupe:
        return {"ok": False, "skipped": True, "reason": "deduped"}
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx missing"}
    results = []
    for ch in cfg.get("channels") or []:
        url = str(ch.get("url") or "").strip()
        if not url:
            continue
        payload = _build_payload(str(ch.get("template") or "json"), title, body)
        headers = dict(ch.get("headers") or {})
        headers.setdefault("Content-Type", "application/json")
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
            results.append({"id": ch.get("id"), "status": resp.status_code, "ok": resp.status_code < 400})
        except Exception as e:
            results.append({"id": ch.get("id"), "ok": False, "error": str(e)[:200]})
    if any(r.get("ok") for r in results):
        _last_push[key] = now
    return {"ok": any(r.get("ok") for r in results), "results": results}

def push_inspection_alert(report: dict[str, Any]) -> dict[str, Any]:
    s = report.get("summary") or {}
    title = f"[Kylin Ops] inspection {report.get('suite_name', '')} failed"
    body = f"failed {s.get('failed')}/{s.get('total')} worst={s.get('worst_grade')} run={report.get('run_id')}"
    return push_webhook(title, body, grade=str(s.get("worst_grade") or "P1"))

def push_aggregated_alerts(agg: dict[str, Any]) -> dict[str, Any]:
    display = agg.get("display_alerts") or []
    p01 = [a for a in display if str(a.get("grade", "")).upper() in ("P0", "P1")]
    if not p01:
        return {"ok": False, "skipped": True, "reason": "no P0/P1"}
    title = "[Kylin Ops] aggregated alerts"
    body = "\n".join(f"- [{a.get('grade')}] {a.get('title') or a.get('type')}" for a in p01[:5])
    worst = "P0" if any(a.get("grade") == "P0" for a in p01) else "P1"
    return push_webhook(title, body, grade=worst)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

src = (ROOT / "scripts" / "_health_format_src.py").read_text(encoding="utf-8")
old = """    if tool_trace:
        for entry in tool_trace:
            name = entry.get("tool")"""
new = """    if tool_trace:
        for entry in tool_trace:
            if not isinstance(entry, dict):
                continue
            name = entry.get("tool")"""
if old in src:
    src = src.replace(old, new)
(ROOT / "security_agent" / "agent" / "health_format.py").write_text(src, encoding="utf-8")

trace_js = """import api from './index'

export function fetchTraceMemo(traceId) {
  return api.get(`/trace/${encodeURIComponent(traceId)}/memo`)
}

export function fetchTraceViz(traceId) {
  return api.get(`/trace/${encodeURIComponent(traceId)}`)
}
"""
(ROOT / "frontend" / "src" / "api" / "trace.js").write_text(trace_js, encoding="utf-8")
print("ok")

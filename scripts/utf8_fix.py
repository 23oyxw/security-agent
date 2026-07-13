from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fix_utf16(path: Path) -> None:
    raw = path.read_bytes()
    if len(raw) > 3 and raw[1] == 0:
        path.write_text(raw.decode("utf-16"), encoding="utf-8", newline="\n")
        print("fixed", path)


for rel in [
    "security_agent/agent/trace_memo.py",
    "frontend/src/api/trace.js",
]:
    fix_utf16(ROOT / rel)

(ROOT / "frontend" / "src" / "api" / "trace.js").write_text(
    "import api from './index'\n\n"
    "export function fetchTraceMemo(traceId) {\n"
    "  return api.get('/trace/' + encodeURIComponent(traceId) + '/memo')\n"
    "}\n\n"
    "export function fetchTraceViz(traceId) {\n"
    "  return api.get('/trace/' + encodeURIComponent(traceId))\n"
    "}\n",
    encoding="utf-8",
)
print("done")

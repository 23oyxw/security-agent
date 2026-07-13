from pathlib import Path

Path("security_agent/agent/health_format.py").write_text(
    Path("scripts/_health_format_src.py").read_text(encoding="utf-8"),
    encoding="utf-8",
)
print("ok")

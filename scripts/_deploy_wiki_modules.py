from pathlib import Path

BOUNDARY = Path("security_agent/knowledge/boundary_wiki.py")
LOCAL = Path("security_agent/knowledge/gitee_wiki/local_bundle.py")
BOUNDARY.parent.mkdir(parents=True, exist_ok=True)
LOCAL.parent.mkdir(parents=True, exist_ok=True)

BOUNDARY.write_text(Path("scripts/_boundary_wiki_src.py").read_text(encoding="utf-8"), encoding="utf-8")
LOCAL.write_text(Path("scripts/_local_bundle_src.py").read_text(encoding="utf-8"), encoding="utf-8")
print("ok", BOUNDARY.stat().st_size, LOCAL.stat().st_size)

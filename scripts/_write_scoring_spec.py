from pathlib import Path
SRC = Path("scripts/_scoring_spec_src.py")
DST = Path("security_agent/l5/scoring_spec.py")
DST.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
print("ok", DST.stat().st_size)

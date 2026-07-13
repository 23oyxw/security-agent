from pathlib import Path

src_path = Path(r"C:\Users\oyxw\security-agent\scripts\_scoring_spec_src.py")
out_path = Path(r"C:\Users\oyxw\security-agent\security_agent\l5\scoring_spec.py")

text = src_path.read_text(encoding="utf-8")
text = text.replace(
    "def build_l5_dimension_report(*, raw, shrunk, confidence, sample_count):",
    "def build_l5_dimension_report(*, raw, shrunk, confidence, sample_count, trace_sources=None):",
)
old = '            "sample_count": sample_count,\n        })'
new = '            "sample_count": sample_count,\n            "data_source": (trace_sources or {}).get(ek, "eval"),\n        })'
text = text.replace(old, new)
out_path.write_text(text, encoding="utf-8")
print("ok", out_path.stat().st_size)
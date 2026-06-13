# -*- coding: utf-8 -*-
"""Build tiered markdown bundle for Gitee Wiki upload."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "wiki_export"
OUT.mkdir(parents=True, exist_ok=True)

DOCS = {
    "T0-definition.md": ROOT / "docs/architecture/ENCAPSULATION_TO_L5_ROADMAP.md",
    "T1-pipeline.md": ROOT / "docs/architecture/FIVE_LAYER_PIPELINE.md",
    "T2-math.md": ROOT / "docs/architecture/L5_ANALYTICS.md",
    "T3-workflow.md": ROOT / "data/mcp/workflow_manifest.json",
    "T4-sandbox.md": ROOT / "docs/architecture/ARCHITECTURE_TIER_MAP.md",
    "TIER-INDEX.md": ROOT / "docs/architecture/ARCHITECTURE_TIER_MAP.md",
}

for name, src in DOCS.items():
    if not src.is_file():
        continue
    body = src.read_text(encoding="utf-8")
    header = f"---\ntier: {name.split('-')[0]}\nsource: {src.relative_to(ROOT)}\n---\n\n"
    (OUT / name).write_text(header + body, encoding="utf-8")
    print("exported", OUT / name)

print("done", len(list(OUT.glob('*.md'))), "files")
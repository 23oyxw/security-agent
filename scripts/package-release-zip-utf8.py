#!/usr/bin/env python3
"""Create UTF-8 zip for LoongArch/Kylin (fixes Chinese filename mojibake)."""
from __future__ import annotations

import fnmatch
import os
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
STAMP = datetime.now().strftime("%Y%m%d")
NAME = f"security-agent-v{VERSION}-{STAMP}-utf8"
OUT_DIR = ROOT / "dist"
ZIP_PATH = OUT_DIR / f"{NAME}.zip"

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    ".cursor",
    "node_modules",
    "__pycache__",
    "qt01",
    "aiflowy-main",
    "pgdata",
    "pgdata2",
    "logs",
    "reports",
    ".pytest_cache",
}
EXCLUDE_FILE_PATTERNS = [
    "*.pyc",
    "*.pyo",
    ".env",
    ".streamlit.pid",
    ".api.pid",
    ".litellm.pid",
    "audit.log",
    "traces.db",
    "conversations.db",
]


def norm_rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def excluded(rel: str) -> bool:
    if rel == "dist" or rel.startswith("dist/"):
        return True
    for part in rel.split("/"):
        if part in EXCLUDE_DIR_NAMES or part.endswith(".egg-info"):
            return True
    base = os.path.basename(rel)
    for pat in EXCLUDE_FILE_PATTERNS:
        if fnmatch.fnmatch(base, pat):
            return True
    if rel.startswith("data/") and rel.endswith(".db"):
        return True
    if rel.startswith("data/alerts"):
        return True
    return False


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    count = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            rel_dir = norm_rel(Path(dirpath))
            dirnames[:] = [
                d
                for d in dirnames
                if not excluded(norm_rel(Path(dirpath) / d))
            ]
            for fn in filenames:
                full = Path(dirpath) / fn
                rel = norm_rel(full)
                if excluded(rel):
                    continue
                info = zipfile.ZipInfo(rel)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.flag_bits |= 0x800
                zf.writestr(info, full.read_bytes())
                count += 1

    size_mb = round(ZIP_PATH.stat().st_size / (1024 * 1024), 2)
    print(f"CREATED: {ZIP_PATH}")
    print(f"SIZE_MB: {size_mb}")
    print(f"FILES: {count}")

    checks = [
        "发给小组-使用说明.txt",
        "打开应用.sh",
        "查看API文档.sh",
        "frontend/dist/index.html",
        "scripts/bootstrap-kylin-loongarch.sh",
    ]
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        names = [n.replace("\\", "/") for n in zf.namelist()]
        for target in checks:
            ok = any(n.endswith(target) for n in names)
            print(f"CHECK {target}: {'OK' if ok else 'MISSING'}")


if __name__ == "__main__":
    main()

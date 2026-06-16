"""Single source: read root VERSION file."""
from __future__ import annotations
from pathlib import Path

_ROOT_VERSION = Path(__file__).resolve().parents[1] / "VERSION"


def get_version() -> str:
    if _ROOT_VERSION.is_file():
        return _ROOT_VERSION.read_text(encoding="utf-8").strip()
    return "0.0.0"


__version__ = get_version()

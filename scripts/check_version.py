#!/usr/bin/env python3
"""Ensure VERSION matches pyproject, frontend, and package __version__."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK: {msg}")


def main() -> None:
    if not VERSION:
        fail("VERSION file empty")

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    if not m or m.group(1) != VERSION:
        fail(f"pyproject.toml version != {VERSION}")

    pkg = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    if pkg.get("version") != VERSION:
        fail(f"frontend/package.json version != {VERSION}")

    sys.path.insert(0, str(ROOT))
    from security_agent.version import __version__

    if __version__ != VERSION:
        fail(f"security_agent.version {__version__} != {VERSION}")

    app_src = (ROOT / "security_agent/api/app.py").read_text(encoding="utf-8")
    if "__version__" not in app_src:
        fail("app.py must use __version__ from security_agent.version")

    init_py = (ROOT / "security_agent/api/__init__.py").read_text(encoding="utf-8")
    if "from security_agent.version import __version__" not in init_py:
        fail("security_agent/api/__init__.py must import __version__ from security_agent.version")

    ok(f"version {VERSION} aligned")


if __name__ == "__main__":
    main()

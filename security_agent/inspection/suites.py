"""Load inspection suite YAML files."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from security_agent import config

SUITES_DIR = config.DATA_DIR / "inspection" / "suites"

def list_suite_ids() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not SUITES_DIR.is_dir():
        return items
    for path in sorted(SUITES_DIR.glob("*.yaml")):
        suite = load_suite_file(path)
        items.append({"id": suite.get("id", path.stem), "name": suite.get("name", path.stem),
            "description": suite.get("description", ""), "case_count": len(suite.get("cases") or [])})
    return items

def load_suite(suite_id: str) -> dict[str, Any]:
    path = SUITES_DIR / f"{suite_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(suite_id)
    return load_suite_file(path)

def load_suite_file(path: Path) -> dict[str, Any]:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(path)
    data.setdefault("id", path.stem)
    return data

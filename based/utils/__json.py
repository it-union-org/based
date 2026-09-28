"""
    Desc: read and write yaml/json configuration and data files
    Creator: Kirosha
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
EXTENSIONS = (".yaml", ".yml", ".json")


def read(name: str) -> dict:
    for ext in EXTENSIONS:
        path = CONFIG_DIR / f"{name}{ext}"
        if path.exists():
            return read_path(path)
    return {}


def read_path(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    return yaml.safe_load(text) or {}


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")

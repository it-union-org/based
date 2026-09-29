"""
    Desc: loads prompt templates for modules, first from the repo, then from the cache
    Creator: Kirosha
"""

from __future__ import annotations

from pathlib import Path

from based.utils.__assets import prompts_dir

MODULES_ROOT = Path(__file__).resolve().parent.parent / "modules"


def load_prompt(module: str, name: str) -> str | None:
    filename = name if name.endswith(".md") else f"{name}.md"

    local = MODULES_ROOT / module / "prompts" / filename
    if local.exists():
        return local.read_text(encoding="utf-8")

    cached = prompts_dir(module) / filename
    if cached.exists():
        return cached.read_text(encoding="utf-8")

    return None

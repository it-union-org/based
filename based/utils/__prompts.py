"""
    Desc: loads prompt templates for modules from the assets cache
    Creator: Kirosha
"""

from __future__ import annotations

from based.utils.__assets import prompts_dir


def load_prompt(module: str, name: str) -> str | None:
    filename = name if name.endswith(".md") else f"{name}.md"
    path = prompts_dir(module) / filename
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")

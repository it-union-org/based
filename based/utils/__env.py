"""
    Desc: thin wrapper over python-dotenv for reading environment configuration
    Creator: Kirosha
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

ENV_PATH = Path(__file__).resolve().parent.parent / "config" / ".env"
ENV_KEYS = ("OLLAMA_HOST", "ASSETS_BASE_URL", "ASSETS_VERSION")


def read_env() -> dict[str, str]:
    values = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    result: dict[str, str] = {}
    for key in ENV_KEYS:
        value = values.get(key) or os.environ.get(key)
        if value is not None:
            result[key] = value
    return result

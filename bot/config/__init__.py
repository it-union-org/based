"""
    Desc: bot configuration read from bot/config/*.yaml and .env
    Creator: Kirosha
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import dotenv_values

_HERE = Path(__file__).resolve().parent
_ENV_PATH = _HERE / ".env"


def _read_yaml(name: str) -> dict:
    path = _HERE / f"{name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _read_env() -> dict:
    values = dotenv_values(_ENV_PATH) if _ENV_PATH.exists() else {}
    for key in (
        "BOT_TOKEN",
        "BOT_CACHE_DIR",
        "BOT_ALLOWED_USER_IDS",
        "OLLAMA_HOST",
        "ASSETS_BASE_URL",
        "ASSETS_VERSION",
    ):
        if key not in values and key in os.environ:
            values[key] = os.environ[key]
    return {k: v for k, v in values.items() if v is not None}


class BotConfig:
    def __init__(self) -> None:
        bot = _read_yaml("bot")
        security = _read_yaml("security")
        env = _read_env()

        limits = bot.get("limits", {})
        session = bot.get("session", {})
        rate = bot.get("rate_limit", {})
        reminders = bot.get("reminders", {})
        cache = bot.get("cache", {})

        self.token: str = env.get("BOT_TOKEN", "")
        self.cache_dir: Path = Path(
            os.path.expanduser(env.get("BOT_CACHE_DIR") or cache.get("dir", "~/.cache/based-bot"))
        )
        self.db_path: Path = self.cache_dir / "sessions.db"
        self.allowed_user_ids: list[str] = [
            item.strip()
            for item in env.get("BOT_ALLOWED_USER_IDS", "").split(",")
            if item.strip()
        ]

        self.ollama_host: str = env.get("OLLAMA_HOST", "http://localhost:11434")
        self.assets_base_url: str = env.get(
            "ASSETS_BASE_URL", "https://github.com/it-union-org/assets/releases/download"
        )
        self.assets_version: str = env.get("ASSETS_VERSION", "v1.0.0")

        self.max_file_size_mb: int = int(limits.get("max_file_size_mb", 200))
        self.max_total_size_mb: int = int(limits.get("max_total_size_mb", 1000))
        self.max_files_per_session: int = int(limits.get("max_files_per_session", 30))
        self.max_text_length: int = int(limits.get("max_text_length", 10000))

        self.session_timeout_minutes: int = int(session.get("timeout_minutes", 60))
        self.schedule_upload_timeout_seconds: int = int(
            session.get("schedule_upload_timeout_seconds", 60)
        )

        self.rate_per_minute: int = int(rate.get("per_minute", 60))
        self.rate_per_hour: int = int(rate.get("per_hour", 300))
        self.rate_ban_seconds: int = int(rate.get("ban_seconds", 30))

        self.reminder_tick_seconds: int = int(reminders.get("tick_seconds", 10))

        self.allowed_extensions: set[str] = set(security.get("allowed_extensions", []))
        self.blocked_extensions: set[str] = set(security.get("blocked_extensions", []))


config = BotConfig()

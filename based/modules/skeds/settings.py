"""
    Desc: settings for the skeds module
    Creator: Kirosha
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SkedsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SKEDS_", extra="ignore")

    max_retries: int = 3

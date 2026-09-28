"""
    Desc: settings for the notes module
    Creator: Kirosha
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class NotesSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTES_", extra="ignore")

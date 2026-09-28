"""
    Desc: settings for the tasks module
    Creator: Kirosha
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class TasksSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TASKS_", extra="ignore")

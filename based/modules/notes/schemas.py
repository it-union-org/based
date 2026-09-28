"""
    Desc: schemas for the notes module
    Creator: Kirosha
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, field_validator


class NoteRequest(BaseModel):
    audio_paths: list[Path] = []
    image_paths: list[Path] = []
    presentation_path: Path | None = None
    raw_text: str | None = None
    subject_name: str

    @field_validator("audio_paths", "image_paths", mode="before")
    @classmethod
    def __ensure_list(cls, value):
        return value or []


class NotesHealth(str, Enum):
    IDLE = "idle"
    RUNNING_TRANSCRIPTION = "running_transcription"
    RUNNING_VISION = "running_vision"
    RUNNING_SUMMARY = "running_summary"
    UNAVAILABLE = "unavailable"

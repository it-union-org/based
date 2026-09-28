"""
    Desc: public api for the notes module
    Creator: Kirosha
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Awaitable, Callable

from based.modules.notes.pipeline import Pipeline
from based.modules.notes.schemas import NoteRequest
from based.modules.notes.settings import NotesSettings
from based.utils.__health import HealthStatus
from based.utils.__llm import get_tags

__all__ = ["NotesAPI", "NoteRequest"]

ProgressCallback = Callable[[str], Awaitable[None]]


class NotesAPI:
    def __init__(self, settings: NotesSettings | None = None) -> None:
        self.settings = settings or NotesSettings()
        self.__pipeline = Pipeline(self.settings)

    async def create_note(
        self,
        request: NoteRequest,
        progress_cb: ProgressCallback | None = None,
    ) -> Path | None:
        return await self.__pipeline.create_note(request, progress_cb)

    async def create_note_from_text(
        self,
        text: str,
        subject_name: str,
        progress_cb: ProgressCallback | None = None,
    ) -> Path | None:
        return await self.__pipeline.create_note_from_text(text, subject_name, progress_cb)

    def health_check(self) -> dict:
        if self.__pipeline.health.status == HealthStatus.RUNNING:
            return self.__pipeline.health.snapshot()
        if shutil.which("ffmpeg") is None:
            return {
                "status": "unavailable",
                "current": None,
                "last": None,
                "errors": ["ffmpeg not found in PATH"],
                "warnings": [],
            }
        if get_tags() is None:
            return {
                "status": "unavailable",
                "current": None,
                "last": None,
                "errors": ["ollama unreachable"],
                "warnings": [],
            }
        return self.__pipeline.health.snapshot()

"""
    Desc: public api for the skeds schedule extraction module
    Creator: Kirosha
"""

from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from based.modules.skeds.pipeline import Pipeline
from based.modules.skeds.schemas import Lesson, Schedule, ScheduleRequest
from based.modules.skeds.settings import SkedsSettings
from based.utils.__db import get_db
from based.utils.__health import HealthStatus
from based.utils.__llm import get_tags

__all__ = ["SkedsAPI", "ScheduleRequest", "Schedule", "Lesson"]

ProgressCallback = Callable[[str], Awaitable[None]]


class SkedsAPI:
    def __init__(self, settings: SkedsSettings | None = None) -> None:
        self.settings = settings or SkedsSettings()
        self.db = get_db()
        self.__pipeline = Pipeline(self.settings, self.db)

    async def parse(
        self,
        source: Path,
        group_name: str | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> Schedule | None:
        return await self.__pipeline.parse(
            ScheduleRequest(source=source, group_name=group_name),
            progress_cb,
        )

    def get_day(self, group_name: str, date: str) -> list[dict]:
        return self.db.get_lessons(group_name, date)

    def get_range(self, group_name: str, from_date: str, to_date: str) -> list[dict]:
        return self.db.get_lessons_range(group_name, from_date, to_date)

    def get_day_all(self, date: str) -> list[dict]:
        return self.db.get_lessons_all(date)

    def get_range_all(self, from_date: str, to_date: str) -> list[dict]:
        return self.db.get_lessons_range_all(from_date, to_date)

    def health_check(self) -> dict:
        if self.__pipeline.health.status == HealthStatus.RUNNING:
            return self.__pipeline.health.snapshot()
        if get_tags() is None:
            return {
                "status": "unavailable",
                "current": None,
                "last": None,
                "errors": ["ollama unreachable"],
                "warnings": [],
            }
        return self.__pipeline.health.snapshot()

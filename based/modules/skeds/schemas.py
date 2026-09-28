"""
    Desc: schemas for the skeds module
    Creator: Kirosha
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class Lesson(BaseModel):
    id: str
    group_name: str | None = None
    subject: str
    teacher: str | None = None
    room: str | None = None
    address: str | None = None
    date: str
    start_time: str
    end_time: str
    lesson_type: str | None = None
    raw_type: str | None = None
    subgroup: str | None = None
    link: str | None = None


class Schedule(BaseModel):
    group_name: str
    from_date: str
    to_date: str
    source: str
    lessons: list[Lesson]
    parsed_at: str


class ScheduleRequest(BaseModel):
    source: Path
    group_name: str | None = None

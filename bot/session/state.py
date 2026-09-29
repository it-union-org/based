"""
    Desc: session states and data model
    Creator: Kirosha
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SessionState(str, Enum):
    IDLE = "idle"
    AWAITING_SUBJECT = "awaiting_subject"
    AWAITING_TYPE = "awaiting_type"
    COLLECTING_FILES = "collecting_files"
    PROCESSING = "processing"
    AWAITING_DIGEST_TIME = "awaiting_digest_time"
    AWAITING_ALERT_MIN = "awaiting_alert_min"
    AWAITING_TASK_BEFORE_TIME = "awaiting_task_before_time"
    AWAITING_TASK_TODAY_TIME = "awaiting_task_today_time"
    AWAITING_SCHEDULE_FILE = "awaiting_schedule_file"
    AWAITING_TASK_ADD = "awaiting_task_add"


LESSON_TYPES = ("лекция", "семинар", "лабораторная", "другое")


@dataclass
class SessionFile:
    file_id: str
    file_type: str
    local_path: str
    size_bytes: int
    added_at: str


@dataclass
class Session:
    user_id: str
    state: SessionState = SessionState.IDLE
    subject: str | None = None
    lesson_type: str | None = None
    files: list[SessionFile] = field(default_factory=list)
    status_message_id: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    def count(self, file_type: str) -> int:
        return sum(1 for f in self.files if f.file_type == file_type)

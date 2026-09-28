"""
    Desc: schemas for the tasks module
    Creator: Kirosha
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class TaskStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"


class Task(BaseModel):
    user_id: str
    task_number: int
    subject: str
    due_date: str
    lesson_date: str | None = None
    description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: str
    completed_at: str | None = None

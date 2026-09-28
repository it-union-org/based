"""
    Desc: public api for the tasks homework tracking module
    Creator: Kirosha
"""

from __future__ import annotations

from based.modules.tasks.schemas import Task, TaskStatus
from based.modules.tasks.settings import TasksSettings
from based.utils.__db import get_db

__all__ = ["TasksAPI", "Task", "TaskStatus"]


class TasksAPI:
    def __init__(self, settings: TasksSettings | None = None) -> None:
        self.settings = settings or TasksSettings()
        self.db = get_db()

    def add(
        self,
        user_id: str,
        subject: str,
        due_date: str,
        description: str,
        lesson_date: str | None = None,
    ) -> Task:
        return Task(**self.db.add_task(user_id, subject, due_date, description, lesson_date))

    def get(self, user_id: str, task_number: int) -> Task | None:
        row = self.db.get_task(user_id, task_number)
        return Task(**row) if row else None

    def list(self, user_id: str, status: str | None = None, due_date: str | None = None) -> list[Task]:
        return [Task(**row) for row in self.db.list_tasks(user_id, status, due_date)]

    def today(self, user_id: str) -> list[Task]:
        return [Task(**row) for row in self.db.tasks_today(user_id)]

    def tomorrow(self, user_id: str) -> list[Task]:
        return [Task(**row) for row in self.db.tasks_tomorrow(user_id)]

    def week(self, user_id: str) -> list[Task]:
        return [Task(**row) for row in self.db.tasks_week(user_id)]

    def mark_done(self, user_id: str, task_number: int) -> None:
        self.db.mark_done(user_id, task_number)

    def mark_cancelled(self, user_id: str, task_number: int) -> None:
        self.db.mark_cancelled(user_id, task_number)

    def cancel_for_lesson(self, user_id: str, subject: str, lesson_date: str) -> int:
        return self.db.cancel_tasks_for_lesson(user_id, subject, lesson_date)

    def subjects(self, user_id: str) -> list[str]:
        return self.db.subjects_for_user(user_id)

    def health_check(self) -> dict:
        try:
            self.db.get_group("__health_check__")
        except Exception as exc:
            return {
                "status": "unavailable",
                "current": None,
                "last": None,
                "errors": [f"{exc.__class__.__name__}: {exc}"],
                "warnings": [],
            }
        return {"status": "idle", "current": None, "last": None, "errors": [], "warnings": []}

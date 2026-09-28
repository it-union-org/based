"""
    Desc: global sqlite manager for groups, schedules, lessons and tasks
    Creator: Kirosha
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from based.config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    tenant       TEXT,
    source       TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_groups (
    user_id      TEXT PRIMARY KEY,
    group_name   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name   TEXT NOT NULL,
    from_date    TEXT NOT NULL,
    to_date      TEXT NOT NULL,
    source       TEXT NOT NULL,
    parsed_at    TEXT NOT NULL,
    raw_hash     TEXT,
    UNIQUE (group_name, from_date, to_date)
);

CREATE TABLE IF NOT EXISTS lessons (
    id           TEXT PRIMARY KEY,
    schedule_id  INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    group_name   TEXT NOT NULL,
    subject      TEXT NOT NULL,
    teacher      TEXT,
    room         TEXT,
    address      TEXT,
    date         TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL,
    lesson_type  TEXT,
    raw_type     TEXT,
    subgroup     TEXT,
    link         TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    user_id       TEXT NOT NULL,
    task_number   INTEGER NOT NULL,
    subject       TEXT NOT NULL,
    due_date      TEXT NOT NULL,
    lesson_date   TEXT,
    description   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TEXT NOT NULL,
    completed_at  TEXT,
    PRIMARY KEY (user_id, task_number)
);

CREATE INDEX IF NOT EXISTS idx_lessons_date        ON lessons(date);
CREATE INDEX IF NOT EXISTS idx_lessons_group_date  ON lessons(group_name, date);
CREATE INDEX IF NOT EXISTS idx_lessons_start       ON lessons(date, start_time);
CREATE INDEX IF NOT EXISTS idx_tasks_user_status   ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_user_due      ON tasks(user_id, due_date);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _rows(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


class BasedDB:
    def __init__(self, path: Path | None = None) -> None:
        self.__path = path or config.db_path
        self.__path.parent.mkdir(parents=True, exist_ok=True)
        self.__conn = sqlite3.connect(str(self.__path), check_same_thread=False)
        self.__conn.row_factory = sqlite3.Row
        self.__conn.execute("PRAGMA foreign_keys = ON")
        self.__conn.executescript(SCHEMA)
        self.__conn.commit()

    def upsert_group(self, name: str, tenant: str | None = None, source: str | None = None) -> None:
        self.__conn.execute(
            """
            INSERT INTO groups (id, name, tenant, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET tenant = excluded.tenant, source = excluded.source
            """,
            (name, name, tenant, source, _now()),
        )
        self.__conn.commit()

    def get_group(self, name: str) -> dict | None:
        return _row(self.__conn.execute("SELECT * FROM groups WHERE name = ?", (name,)).fetchone())

    def set_user_group(self, user_id: str, group_name: str) -> None:
        self.__conn.execute(
            """
            INSERT INTO user_groups (user_id, group_name, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET group_name = excluded.group_name,
                updated_at = excluded.updated_at
            """,
            (user_id, group_name, _now()),
        )
        self.__conn.commit()

    def get_user_group(self, user_id: str) -> str | None:
        row = self.__conn.execute(
            "SELECT group_name FROM user_groups WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["group_name"] if row else None

    def upsert_schedule(
        self,
        group_name: str,
        from_date: str,
        to_date: str,
        source: str,
        lessons: list[dict],
        raw_hash: str | None = None,
    ) -> int:
        self.__conn.execute(
            """
            INSERT INTO schedules (group_name, from_date, to_date, source, parsed_at, raw_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_name, from_date, to_date) DO UPDATE SET
                source = excluded.source, parsed_at = excluded.parsed_at, raw_hash = excluded.raw_hash
            """,
            (group_name, from_date, to_date, source, _now(), raw_hash),
        )
        row = self.__conn.execute(
            "SELECT id FROM schedules WHERE group_name = ? AND from_date = ? AND to_date = ?",
            (group_name, from_date, to_date),
        ).fetchone()
        schedule_id = row["id"]
        self.__conn.execute("DELETE FROM lessons WHERE schedule_id = ?", (schedule_id,))
        for lesson in lessons:
            self.__conn.execute(
                """
                INSERT INTO lessons (
                    id, schedule_id, group_name, subject, teacher, room, address,
                    date, start_time, end_time, lesson_type, raw_type, subgroup, link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lesson["id"],
                    schedule_id,
                    group_name,
                    lesson["subject"],
                    lesson.get("teacher"),
                    lesson.get("room"),
                    lesson.get("address"),
                    lesson["date"],
                    lesson["start_time"],
                    lesson["end_time"],
                    lesson.get("lesson_type"),
                    lesson.get("raw_type"),
                    lesson.get("subgroup"),
                    lesson.get("link"),
                ),
            )
        self.__conn.commit()
        return schedule_id

    def get_lessons(self, group_name: str, date: str) -> list[dict]:
        return _rows(
            self.__conn.execute(
                "SELECT * FROM lessons WHERE group_name = ? AND date = ? ORDER BY start_time",
                (group_name, date),
            ).fetchall()
        )

    def get_lessons_range(self, group_name: str, from_date: str, to_date: str) -> list[dict]:
        return _rows(
            self.__conn.execute(
                "SELECT * FROM lessons WHERE group_name = ? AND date BETWEEN ? AND ? ORDER BY date, start_time",
                (group_name, from_date, to_date),
            ).fetchall()
        )

    def get_upcoming_for_group(self, group_name: str, minutes: int = 5) -> list[dict]:
        now = datetime.now()
        target = (now + timedelta(minutes=minutes)).strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        return _rows(
            self.__conn.execute(
                "SELECT * FROM lessons WHERE group_name = ? AND date = ? AND start_time = ?",
                (group_name, today, target),
            ).fetchall()
        )

    def add_task(
        self,
        user_id: str,
        subject: str,
        due_date: str,
        description: str,
        lesson_date: str | None = None,
    ) -> dict:
        row = self.__conn.execute(
            "SELECT COALESCE(MAX(task_number), 0) + 1 AS next FROM tasks WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        task_number = row["next"]
        self.__conn.execute(
            """
            INSERT INTO tasks (
                user_id, task_number, subject, due_date, lesson_date,
                description, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (user_id, task_number, subject, due_date, lesson_date, description, _now()),
        )
        self.__conn.commit()
        return self.get_task(user_id, task_number)

    def get_task(self, user_id: str, task_number: int) -> dict | None:
        return _row(
            self.__conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND task_number = ?",
                (user_id, task_number),
            ).fetchone()
        )

    def list_tasks(self, user_id: str, status: str | None = None, due_date: str | None = None) -> list[dict]:
        query = "SELECT * FROM tasks WHERE user_id = ?"
        params: list = [user_id]
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        if due_date is not None:
            query += " AND due_date = ?"
            params.append(due_date)
        query += " ORDER BY due_date, task_number"
        return _rows(self.__conn.execute(query, params).fetchall())

    def tasks_today(self, user_id: str) -> list[dict]:
        return self.list_tasks(user_id, due_date=datetime.now().strftime("%Y-%m-%d"))

    def tasks_tomorrow(self, user_id: str) -> list[dict]:
        return self.list_tasks(
            user_id, due_date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        )

    def tasks_week(self, user_id: str) -> list[dict]:
        today = datetime.now()
        week_end = today + timedelta(days=6)
        return _rows(
            self.__conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND due_date BETWEEN ? AND ? ORDER BY due_date",
                (user_id, today.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")),
            ).fetchall()
        )

    def mark_done(self, user_id: str, task_number: int) -> None:
        self.__conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ? WHERE user_id = ? AND task_number = ?",
            (_now(), user_id, task_number),
        )
        self.__conn.commit()

    def mark_cancelled(self, user_id: str, task_number: int) -> None:
        self.__conn.execute(
            "UPDATE tasks SET status = 'cancelled', completed_at = ? WHERE user_id = ? AND task_number = ?",
            (_now(), user_id, task_number),
        )
        self.__conn.commit()

    def cancel_tasks_for_lesson(self, user_id: str, subject: str, lesson_date: str) -> int:
        cursor = self.__conn.execute(
            """
            UPDATE tasks SET status = 'cancelled', completed_at = ?
            WHERE user_id = ? AND subject = ? AND lesson_date = ? AND status = 'pending'
            """,
            (_now(), user_id, subject, lesson_date),
        )
        self.__conn.commit()
        return cursor.rowcount


    def delete_all_tasks(self, user_id: str) -> int:
        cursor = self.__conn.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        self.__conn.commit()
        return cursor.rowcount

    def delete_schedule(self, group_name: str) -> int:
        self.__conn.execute("DELETE FROM lessons WHERE group_name = ?", (group_name,))
        cursor = self.__conn.execute("DELETE FROM schedules WHERE group_name = ?", (group_name,))
        self.__conn.commit()
        return cursor.rowcount

    def delete_lessons_started_before(self, hhmm: str, date: str) -> int:
        cursor = self.__conn.execute(
            "DELETE FROM lessons WHERE date = ? AND start_time <= ?",
            (date, hhmm),
        )
        self.__conn.commit()
        return cursor.rowcount

    def list_groups(self) -> list[str]:
        rows = self.__conn.execute("SELECT name FROM groups ORDER BY name").fetchall()
        return [row["name"] for row in rows]

    def count_users(self) -> int:
        row = self.__conn.execute("SELECT COUNT(DISTINCT user_id) AS n FROM tasks").fetchone()
        return int(row["n"]) if row else 0

    def count_notes(self) -> int:
        return 0

    def count_tasks(self, user_id: str | None = None) -> int:
        if user_id:
            row = self.__conn.execute("SELECT COUNT(*) AS n FROM tasks WHERE user_id = ?", (user_id,)).fetchone()
        else:
            row = self.__conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()
        return int(row["n"]) if row else 0

    def get_lessons_upcoming(self, group_name: str, minutes: int) -> list[dict]:
        now = datetime.now()
        target = (now + timedelta(minutes=minutes)).strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        return _rows(
            self.__conn.execute(
                "SELECT * FROM lessons WHERE group_name = ? AND date = ? AND start_time = ?",
                (group_name, today, target),
            ).fetchall()
        )

    def get_lessons_at(self, hhmm: str, date: str) -> list[dict]:
        return _rows(
            self.__conn.execute(
                "SELECT * FROM lessons WHERE date = ? AND start_time = ?",
                (date, hhmm),
            ).fetchall()
        )

    def subjects_for_user(self, user_id: str) -> list[str]:
        group_name = self.get_user_group(user_id)
        if not group_name:
            return []
        rows = self.__conn.execute(
            "SELECT DISTINCT subject FROM lessons WHERE group_name = ?", (group_name,)
        ).fetchall()
        return [row["subject"] for row in rows]


_DB_CACHE: dict[str, BasedDB] = {}


def get_db(path: Path | None = None) -> BasedDB:
    key = str(path or config.db_path)
    if key not in _DB_CACHE:
        _DB_CACHE[key] = BasedDB(path)
    return _DB_CACHE[key]

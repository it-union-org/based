"""
    Desc: sqlite storage for sessions, files, settings and reminders
    Creator: Kirosha
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from bot.config import config
from bot.session.state import Session, SessionFile, SessionState

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    user_id           TEXT PRIMARY KEY,
    state             TEXT NOT NULL,
    subject           TEXT,
    lesson_type       TEXT,
    status_message_id TEXT,
    started_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_files (
    user_id     TEXT NOT NULL,
    file_id     TEXT NOT NULL,
    file_type   TEXT NOT NULL,
    local_path  TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL,
    added_at    TEXT NOT NULL,
    PRIMARY KEY (user_id, file_id)
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id             TEXT PRIMARY KEY,
    chat_id             TEXT,
    group_name          TEXT,
    digest_enabled      INTEGER NOT NULL DEFAULT 0,
    digest_time         TEXT,
    lesson_alert_min    INTEGER,
    task_day_before     INTEGER NOT NULL DEFAULT 0,
    task_day_before_at  TEXT,
    task_due_today      INTEGER NOT NULL DEFAULT 0,
    task_due_today_at   TEXT,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    kind       TEXT NOT NULL,
    payload    TEXT,
    fire_at    TEXT NOT NULL,
    sent_at    TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reminders_fire ON reminders(fire_at);
CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id);
"""


def _now() -> str:
    return datetime.now().isoformat()


class Storage:
    def __init__(self, path: Path | None = None) -> None:
        self.__path__ = path or config.db_path
        self.__path__.parent.mkdir(parents=True, exist_ok=True)
        self.__conn = sqlite3.connect(str(self.__path__), check_same_thread=False)
        self.__conn.row_factory = sqlite3.Row
        self.__conn.executescript(SCHEMA)
        self.__conn.commit()
        self.__migrate()

    def __migrate(self) -> None:
        existing = {row[1] for row in self.__conn.execute("PRAGMA table_info(user_settings)")}
        columns = [
            ("chat_id", "TEXT"),
            ("task_day_before", "INTEGER NOT NULL DEFAULT 0"),
            ("task_day_before_at", "TEXT"),
            ("task_due_today", "INTEGER NOT NULL DEFAULT 0"),
            ("task_due_today_at", "TEXT"),
        ]
        added = False
        for name, definition in columns:
            if name in existing:
                continue
            self.__conn.execute(f"ALTER TABLE user_settings ADD COLUMN {name} {definition}")
            added = True
        if added:
            self.__conn.commit()

    def get_session(self, user_id: str) -> Session:
        row = self.__conn.execute(
            "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return Session(user_id=user_id)
        session = Session(
            user_id=user_id,
            state=SessionState(row["state"]),
            subject=row["subject"],
            lesson_type=row["lesson_type"],
            status_message_id=row["status_message_id"],
            started_at=row["started_at"],
            updated_at=row["updated_at"],
        )
        session.files = self.__files(user_id)
        return session

    def save_session(self, session: Session) -> None:
        session.touch()
        self.__conn.execute(
            """
            INSERT INTO sessions (user_id, state, subject, lesson_type, status_message_id, started_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                state = excluded.state,
                subject = excluded.subject,
                lesson_type = excluded.lesson_type,
                status_message_id = excluded.status_message_id,
                updated_at = excluded.updated_at
            """,
            (
                session.user_id,
                session.state.value,
                session.subject,
                session.lesson_type,
                session.status_message_id,
                session.started_at,
                session.updated_at,
            ),
        )
        self.__conn.commit()

    def list_active_sessions(self) -> list[dict]:
        rows = self.__conn.execute(
            "SELECT user_id, state, updated_at FROM sessions WHERE state != 'idle'"
        ).fetchall()
        return [dict(row) for row in rows]

    def add_file(self, user_id: str, file: SessionFile) -> None:
        self.__conn.execute(
            """
            INSERT OR REPLACE INTO session_files
            (user_id, file_id, file_type, local_path, size_bytes, added_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, file.file_id, file.file_type, file.local_path, file.size_bytes, file.added_at),
        )
        self.__conn.commit()

    def clear_files(self, user_id: str) -> None:
        self.__conn.execute("DELETE FROM session_files WHERE user_id = ?", (user_id,))
        self.__conn.commit()

    def __files(self, user_id: str) -> list[SessionFile]:
        rows = self.__conn.execute(
            "SELECT * FROM session_files WHERE user_id = ? ORDER BY added_at", (user_id,)
        ).fetchall()
        return [
            SessionFile(
                file_id=row["file_id"],
                file_type=row["file_type"],
                local_path=row["local_path"],
                size_bytes=row["size_bytes"],
                added_at=row["added_at"],
            )
            for row in rows
        ]

    def add_user_settings_if_missing(self, user_id: str) -> None:
        existing = self.__conn.execute(
            "SELECT user_id FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing is None:
            self.__conn.execute(
                "INSERT INTO user_settings (user_id, updated_at) VALUES (?, ?)",
                (user_id, _now()),
            )
            self.__conn.commit()

    def set_user_setting(self, user_id: str, key: str, value) -> None:
        allowed = {
            "chat_id", "group_name", "digest_enabled", "digest_time",
            "lesson_alert_min", "task_day_before", "task_day_before_at",
            "task_due_today", "task_due_today_at",
        }
        if key not in allowed:
            return
        self.add_user_settings_if_missing(user_id)
        self.__conn.execute(
            f"UPDATE user_settings SET {key} = ?, updated_at = ? WHERE user_id = ?",
            (value, _now(), user_id),
        )
        self.__conn.commit()

    def get_user_settings(self, user_id: str) -> dict:
        row = self.__conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else {}

    def list_user_settings(self) -> list[tuple[str, dict]]:
        rows = self.__conn.execute("SELECT * FROM user_settings").fetchall()
        return [(row["user_id"], dict(row)) for row in rows]

    def add_reminder(self, user_id: str, kind: str, payload: dict, fire_at: str) -> int:
        cursor = self.__conn.execute(
            "INSERT INTO reminders (user_id, kind, payload, fire_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, kind, json.dumps(payload, ensure_ascii=False), fire_at, _now()),
        )
        self.__conn.commit()
        return cursor.lastrowid or 0

    def due_reminders(self, now_iso: str) -> list[dict]:
        try:
            now = datetime.fromisoformat(now_iso)
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)
        except ValueError:
            return []

        rows = self.__conn.execute(
            "SELECT * FROM reminders WHERE sent_at IS NULL ORDER BY fire_at"
        ).fetchall()

        result: list[dict] = []
        for row in rows:
            try:
                fire_at = datetime.fromisoformat(row["fire_at"])
                if fire_at.tzinfo is not None:
                    fire_at = fire_at.replace(tzinfo=None)
            except (ValueError, TypeError):
                continue
            if fire_at <= now:
                result.append(dict(row))
        return result

    def mark_reminder_sent(self, reminder_id: int) -> None:
        self.__conn.execute(
            "UPDATE reminders SET sent_at = ? WHERE id = ?",
            (_now(), reminder_id),
        )
        self.__conn.commit()

    def purge_stale_reminders(self, now_iso: str, tolerance_seconds: int = 300) -> None:
        try:
            now = datetime.fromisoformat(now_iso)
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)
        except ValueError:
            return
        cutoff = (now - timedelta(seconds=tolerance_seconds)).isoformat()

        rows = self.__conn.execute(
            "SELECT id, fire_at FROM reminders WHERE sent_at IS NULL"
        ).fetchall()
        stale_ids: list[int] = []
        for row in rows:
            try:
                fire_at = datetime.fromisoformat(row["fire_at"])
                if fire_at.tzinfo is not None:
                    fire_at = fire_at.replace(tzinfo=None)
            except (ValueError, TypeError):
                continue
            if fire_at < datetime.fromisoformat(cutoff):
                stale_ids.append(row["id"])

        if stale_ids:
            placeholders = ",".join("?" for _ in stale_ids)
            self.__conn.execute(
                f"UPDATE reminders SET sent_at = ? WHERE id IN ({placeholders})",
                (now_iso, *stale_ids),
            )
            self.__conn.commit()

    def has_pending_reminder(self, user_id: str, kind: str, key: str) -> bool:
        payload_like = f'%"key": "{key}"%'
        row = self.__conn.execute(
            "SELECT id FROM reminders WHERE user_id = ? AND kind = ? AND payload LIKE ? AND sent_at IS NULL LIMIT 1",
            (user_id, kind, payload_like),
        ).fetchone()
        return row is not None


    def has_any_reminder(self, user_id: str, kind: str, key: str) -> bool:
        """Проверяет наличие напоминания независимо от статуса отправки."""
        payload_like = f'%"key": "{key}"%'
        row = self.__conn.execute(
            "SELECT id FROM reminders WHERE user_id = ? AND kind = ? AND payload LIKE ? LIMIT 1",
            (user_id, kind, payload_like),
        ).fetchone()
        return row is not None

    def reset_user(self, user_id: str) -> None:
        self.__conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        self.__conn.execute("DELETE FROM session_files WHERE user_id = ?", (user_id,))
        self.__conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        self.__conn.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
        self.__conn.commit()


storage = Storage()

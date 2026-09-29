"""
    Desc: background scheduler that generates and fires notifications
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

from based.modules.tasks.api import TasksAPI
from based.modules.tasks.schemas import TaskStatus
from based.utils.__console import log_warn
from based.utils.__db import get_db

from bot.config import config
from bot.session.state import SessionState
from bot.session.storage import storage
from bot.ui.messages import (
    REMINDER_DIGEST_DATE,
    REMINDER_DIGEST_HEADER,
    REMINDER_DIGEST_ITEM,
    REMINDER_DIGEST_TOTAL,
    REMINDER_LESSON_BODY,
    REMINDER_LESSON_HEADER,
    REMINDER_TASK_BEFORE_HEADER,
    REMINDER_TASK_BEFORE_ITEM,
    REMINDER_TASK_BEFORE_SUBHEADER,
    REMINDER_TASK_BEFORE_TOTAL,
    REMINDER_TASK_TODAY_CLEAR,
    REMINDER_TASK_TODAY_HEADER,
    REMINDER_TASK_TODAY_ITEM,
    REMINDER_TASK_TODAY_PENDING,
    SESSION_TIMEOUT,
)


def current_time() -> datetime:
    return datetime.now()


def current_time_iso() -> str:
    return current_time().isoformat()


async def run_reminders(bot) -> None:
    while True:
        try:
            await tick(bot)
        except Exception as err:
            log_warn(f"scheduler error: {err.__class__.__name__}: {err}")
        await asyncio.sleep(config.reminder_tick_seconds)


async def tick(bot) -> None:
    current = current_time()
    hhmm = current.strftime("%H:%M")
    today = current.strftime("%Y-%m-%d")
    tomorrow = (current + timedelta(days=1)).strftime("%Y-%m-%d")

    generate(current, hhmm, today, tomorrow)
    await fire_due(bot, current)
    cleanup_past_lessons(hhmm, today)
    await cleanup_stale_sessions(bot)


def all_settings() -> list:
    try:
        return storage.list_user_settings()
    except Exception:
        return []


def generate(current: datetime, hhmm: str, today: str, tomorrow: str) -> None:
    for user_id, settings in all_settings():
        generate_digest(user_id, settings, hhmm, today)
        generate_lesson_alerts(user_id, settings, current, today)
        generate_task_alerts(user_id, settings, hhmm, today, tomorrow)


def generate_digest(user_id: str, settings: dict, hhmm: str, today: str) -> None:
    if not settings.get("digest_enabled"):
        return
    if settings.get("digest_time") != hhmm:
        return
    group_name = settings.get("group_name")
    if not group_name:
        return
    key = f"digest:{today}"
    if storage.has_any_reminder(user_id, "digest", key):
        return
    lessons = get_db().get_lessons(group_name, today)
    if not lessons:
        return
    body = format_digest(today, lessons)
    storage.add_reminder(user_id, "digest", {"key": key, "text": body}, current_time_iso())


def generate_lesson_alerts(user_id: str, settings: dict, current: datetime, today: str) -> None:
    alert_min = settings.get("lesson_alert_min")
    if not alert_min:
        return
    group_name = settings.get("group_name")
    if not group_name:
        return
    lessons = get_db().get_lessons(group_name, today)
    window_end = current + timedelta(seconds=config.reminder_tick_seconds)
    for lesson in lessons:
        start = lesson["start_time"]
        start_dt = parse_time(today, start)
        if start_dt is None:
            continue
        alert_dt = start_dt - timedelta(minutes=int(alert_min))
        if not (current <= alert_dt < window_end):
            continue
        key = f"lesson:{today}:{start}:{lesson['subject']}"
        if storage.has_any_reminder(user_id, "lesson", key):
            continue
        body = format_lesson_alert(lesson, int(alert_min))
        storage.add_reminder(user_id, "lesson", {"key": key, "text": body}, alert_dt.isoformat())


def generate_task_alerts(user_id: str, settings: dict, hhmm: str, today: str, tomorrow: str) -> None:
    if settings.get("task_day_before") and settings.get("task_day_before_at") == hhmm:
        key = f"task_before:{tomorrow}"
        if not storage.has_any_reminder(user_id, "task_before", key):
            tasks = pending_for_date(user_id, tomorrow)
            if tasks:
                body = format_tasks_before(tomorrow, tasks)
                storage.add_reminder(
                    user_id, "task_before", {"key": key, "text": body}, current_time_iso()
                )

    if settings.get("task_due_today") and settings.get("task_due_today_at") == hhmm:
        key = f"task_today:{today}"
        if not storage.has_any_reminder(user_id, "task_today", key):
            tasks = all_for_date(user_id, today)
            if tasks:
                body = format_tasks_today(today, tasks)
                storage.add_reminder(
                    user_id, "task_today", {"key": key, "text": body}, current_time_iso()
                )


def pending_for_date(user_id: str, due_date: str) -> list:
    api = TasksAPI()
    return [t for t in api.list(user_id, due_date=due_date) if t.status == TaskStatus.PENDING]


def all_for_date(user_id: str, due_date: str) -> list:
    api = TasksAPI()
    return api.list(user_id, due_date=due_date)


def format_digest(date: str, lessons: list) -> str:
    lines = [REMINDER_DIGEST_HEADER, "", REMINDER_DIGEST_DATE.format(date=date), ""]
    for lesson in lessons:
        lines.append(
            REMINDER_DIGEST_ITEM.format(
                start=lesson["start_time"],
                end=lesson["end_time"],
                subject=lesson["subject"],
                teacher=lesson.get("teacher") or "—",
                room=lesson.get("room") or "—",
            )
        )
        lines.append("")
    lines.append(REMINDER_DIGEST_TOTAL.format(count=len(lessons)))
    return "\n".join(lines)


def format_lesson_alert(lesson: dict, minutes: int) -> str:
    return "\n".join(
        [
            REMINDER_LESSON_HEADER.format(minutes=minutes),
            "",
            REMINDER_LESSON_BODY.format(
                start=lesson["start_time"],
                end=lesson["end_time"],
                subject=lesson["subject"],
                teacher=lesson.get("teacher") or "—",
                room=lesson.get("room") or "—",
            ),
        ]
    )


def format_tasks_before(date: str, tasks: list) -> str:
    lines = [
        REMINDER_TASK_BEFORE_HEADER,
        "",
        REMINDER_TASK_BEFORE_SUBHEADER.format(date=date),
        "",
    ]
    for task in tasks:
        lines.append(
            REMINDER_TASK_BEFORE_ITEM.format(
                number=task.task_number,
                subject=task.subject,
                description=task.description,
                due_date=task.due_date,
            )
        )
        lines.append("")
    lines.append(REMINDER_TASK_BEFORE_TOTAL.format(count=len(tasks)))
    return "\n".join(lines)


def format_tasks_today(date: str, tasks: list) -> str:
    lines = [REMINDER_TASK_TODAY_HEADER, ""]
    pending = 0
    for task in tasks:
        mark = {
            TaskStatus.DONE: "✅",
            TaskStatus.CANCELLED: "❌",
            TaskStatus.PENDING: "⏳",
        }.get(task.status, "•")
        if task.status == TaskStatus.PENDING:
            pending += 1
        lines.append(
            REMINDER_TASK_TODAY_ITEM.format(
                mark=mark,
                number=task.task_number,
                subject=task.subject,
                description=task.description,
                due_date=task.due_date,
            )
        )
        lines.append("")
    if pending:
        word = "задание" if pending == 1 else "задания" if 2 <= pending <= 4 else "заданий"
        lines.append(REMINDER_TASK_TODAY_PENDING.format(count=pending, word=word))
    else:
        lines.append(REMINDER_TASK_TODAY_CLEAR)
    return "\n".join(lines)


async def fire_due(bot, current: datetime) -> None:
    now_iso_str = current.isoformat()
    tolerance = max(config.reminder_tick_seconds * 2, 120)
    storage.purge_stale_reminders(now_iso_str, tolerance_seconds=tolerance)
    due = storage.due_reminders(now_iso_str)
    for reminder in due:
        body = payload_text(reminder)
        chat = chat_for(reminder["user_id"])
        kind = reminder.get("kind", "")
        attachments = []
        if kind == "lesson":
            attachments = [lesson_keyboard()]
        elif kind == "digest":
            attachments = [digest_keyboard()]
        elif kind in ("task_before", "task_today"):
            attachments = [task_keyboard()]
        try:
            await bot.send_message(chat_id=int(chat), text=body, attachments=attachments or None)
        except Exception as err:
            log_warn(f"scheduler send failed: {err.__class__.__name__}: {err}")
        storage.mark_reminder_sent(reminder["id"])


def payload_text(reminder: dict) -> str:
    try:
        payload = json.loads(reminder["payload"] or "{}")
    except ValueError:
        payload = {}
    return payload.get("text") or f"Напоминание: {reminder['kind']}"


def cleanup_past_lessons(hhmm: str, today: str) -> None:
    try:
        get_db().delete_past_lessons(hhmm, today)
    except Exception as err:
        log_warn(f"scheduler cleanup failed: {err.__class__.__name__}: {err}")


def parse_time(date: str, hhmm: str) -> datetime | None:
    try:
        return datetime.strptime(f"{date} {hhmm}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def chat_for(user_id: str) -> str:
    settings = storage.get_user_settings(user_id)
    return str(settings.get("chat_id") or user_id)


async def cleanup_stale_sessions(bot) -> None:
    current = datetime.now()
    threshold = current - timedelta(minutes=config.session_timeout_minutes)
    try:
        rows = storage.list_active_sessions()
    except Exception:
        return
    for row in rows:
        try:
            updated = datetime.fromisoformat(row["updated_at"])
            if updated.tzinfo is not None:
                updated = updated.replace(tzinfo=None)
        except (ValueError, TypeError):
            continue
        if updated > threshold:
            continue
        user_id = row["user_id"]
        session = storage.get_session(user_id)
        if session.state == SessionState.IDLE:
            continue
        session.state = SessionState.IDLE
        session.subject = None
        session.lesson_type = None
        session.status_message_id = None
        storage.save_session(session)
        try:
            chat = chat_for(user_id)
            await bot.send_message(chat_id=int(chat), text=SESSION_TIMEOUT)
        except Exception as err:
            log_warn(f"scheduler session timeout notify failed: {err.__class__.__name__}: {err}")


def lesson_keyboard() -> dict:
    from maxapi.types import ButtonsPayload, CallbackButton

    return ButtonsPayload(
        buttons=[
            [CallbackButton(text="🟢 Открыть расписание", payload="schedule:today")],
            [
                CallbackButton(
                    text="🔕 Отключить напоминания",
                    payload="notif:toggle:lesson_alert_min",
                )
            ],
        ]
    ).pack()


def task_keyboard() -> dict:
    from maxapi.types import ButtonsPayload, CallbackButton

    return ButtonsPayload(
        buttons=[
            [CallbackButton(text="📋 Открыть задачи", payload="tasks:list:pending")],
            [
                CallbackButton(
                    text="🔕 Отключить напоминания",
                    payload="notif:toggle:task_due_today",
                )
            ],
        ]
    ).pack()


def digest_keyboard() -> dict:
    from maxapi.types import ButtonsPayload, CallbackButton

    return ButtonsPayload(
        buttons=[
            [CallbackButton(text="🟢 Открыть расписание", payload="schedule:today")],
        ]
    ).pack()

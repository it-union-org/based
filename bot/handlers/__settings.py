"""
    Desc: settings and notifications
    Creator: Kirosha
"""

from __future__ import annotations

import re

from based.modules.tasks.api import TasksAPI
from based.utils.__db import get_db

from bot.session.files import clear_based_runs, clear_session_files
from bot.session.state import SessionState
from bot.session.storage import storage
from bot.ui import chat_id
from bot.ui.keyboards import confirm_keyboard, main_menu, notifications_menu, settings_menu
from bot.ui.messages import (
    NOTIF_ASK_MINUTES,
    NOTIF_ASK_TIME,
    NOTIF_BAD_MINUTES,
    NOTIF_BAD_TIME,
    NOTIF_MENU,
    NOTIF_SAVED,
    SETTINGS_ALL_CLEARED,
    SETTINGS_CACHE_CLEARED,
    SETTINGS_CONFIRM,
    SETTINGS_SCHEDULE_CLEARED,
    SETTINGS_TASKS_CLEARED,
)

TIME_RE = re.compile(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")

NOTIF_TIME_FIELDS = {
    "digest_time": (SessionState.AWAITING_DIGEST_TIME, "digest_enabled"),
    "task_before_at": (SessionState.AWAITING_TASK_BEFORE_TIME, "task_day_before"),
    "task_today_at": (SessionState.AWAITING_TASK_TODAY_TIME, "task_due_today"),
}


async def route(event, payload: str) -> None:
    action = payload.split(":", 1)[1]
    chat = chat_id(event)
    user = str(event.from_user.user_id)

    if action.startswith("confirm:"):
        await apply(event, action.split(":", 1)[1])
        return
    if action in ("cache", "tasks", "schedule", "all"):
        await event.bot.send_message(
            chat_id=chat, text=SETTINGS_CONFIRM, attachments=[confirm_keyboard(action)]
        )
        return
    if action == "notifications":
        settings = storage.get_user_settings(user)
        await event.bot.send_message(
            chat_id=chat, text=NOTIF_MENU, attachments=[notifications_menu(settings)]
        )


async def handle_notif(event, payload: str) -> bool:
    if not payload.startswith("notif:"):
        return False
    parts = payload.split(":", 2)
    if len(parts) < 3:
        return False
    _, cmd, key = parts
    user = str(event.from_user.user_id)
    chat = chat_id(event)
    storage.add_user_settings_if_missing(user)

    if cmd == "toggle":
        settings = storage.get_user_settings(user)
        current = settings.get(key, 0)
        storage.set_user_setting(user, key, 0 if current else 1)
        await refresh(event, user)
    elif cmd == "set":
        session = storage.get_session(user)
        if key == "alert_min":
            session.state = SessionState.AWAITING_ALERT_MIN
            storage.save_session(session)
            await event.bot.send_message(chat_id=chat, text=NOTIF_ASK_MINUTES)
            return True
        info = NOTIF_TIME_FIELDS.get(key)
        if info is None:
            return False
        session.state = info[0]
        storage.save_session(session)
        await event.bot.send_message(chat_id=chat, text=NOTIF_ASK_TIME)
    return True


async def handle_notif_input(event, text: str) -> bool:
    user = str(event.from_user.user_id)
    session = storage.get_session(user)
    value = text.strip()

    if session.state == SessionState.AWAITING_DIGEST_TIME:
        if not TIME_RE.match(value):
            await event.bot.send_message(chat_id=chat_id(event), text=NOTIF_BAD_TIME)
            return True
        storage.set_user_setting(user, "digest_time", value)
        storage.set_user_setting(user, "digest_enabled", 1)
    elif session.state == SessionState.AWAITING_ALERT_MIN:
        if not value.isdigit():
            await event.bot.send_message(chat_id=chat_id(event), text=NOTIF_BAD_MINUTES)
            return True
        storage.set_user_setting(user, "lesson_alert_min", int(value))
    elif session.state == SessionState.AWAITING_TASK_BEFORE_TIME:
        if not TIME_RE.match(value):
            await event.bot.send_message(chat_id=chat_id(event), text=NOTIF_BAD_TIME)
            return True
        storage.set_user_setting(user, "task_day_before_at", value)
        storage.set_user_setting(user, "task_day_before", 1)
    elif session.state == SessionState.AWAITING_TASK_TODAY_TIME:
        if not TIME_RE.match(value):
            await event.bot.send_message(chat_id=chat_id(event), text=NOTIF_BAD_TIME)
            return True
        storage.set_user_setting(user, "task_due_today_at", value)
        storage.set_user_setting(user, "task_due_today", 1)
    else:
        return False

    session.state = SessionState.IDLE
    storage.save_session(session)
    await refresh(event, user, saved=True)
    return True


async def refresh(event, user: str, saved: bool = False) -> None:
    settings = storage.get_user_settings(user)
    text = NOTIF_SAVED if saved else NOTIF_MENU
    await event.bot.send_message(
        chat_id=chat_id(event), text=text, attachments=[notifications_menu(settings)]
    )


async def apply(event, kind: str) -> None:
    user = str(event.from_user.user_id)
    chat = chat_id(event)
    if kind == "cache":
        clear_session_files(user)
        storage.clear_files(user)
        clear_based_runs()
        await event.bot.send_message(
            chat_id=chat, text=SETTINGS_CACHE_CLEARED, attachments=[main_menu()]
        )
    elif kind == "tasks":
        TasksAPI().db.delete_all_tasks(user)
        await event.bot.send_message(
            chat_id=chat, text=SETTINGS_TASKS_CLEARED, attachments=[main_menu()]
        )
    elif kind == "schedule":
        settings = storage.get_user_settings(user)
        group_name = settings.get("group_name")
        if group_name:
            get_db().delete_schedule(group_name)
        storage.set_user_setting(user, "group_name", None)
        await event.bot.send_message(
            chat_id=chat, text=SETTINGS_SCHEDULE_CLEARED, attachments=[main_menu()]
        )
    elif kind == "all":
        clear_session_files(user)
        storage.clear_files(user)
        clear_based_runs()
        TasksAPI().db.delete_all_tasks(user)
        settings = storage.get_user_settings(user)
        group_name = settings.get("group_name")
        if group_name:
            get_db().delete_schedule(group_name)
        storage.reset_user(user)
        await event.bot.send_message(
            chat_id=chat, text=SETTINGS_ALL_CLEARED, attachments=[main_menu()]
        )

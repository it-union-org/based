"""
    Desc: root menu, help, submenus navigation
    Creator: Kirosha
"""

from __future__ import annotations

from bot.session.state import SessionState
from bot.session.storage import storage
from bot.ui import chat_id, user_id
from bot.ui.keyboards import (
    help_menu,
    main_menu,
    notes_menu,
    schedule_menu,
    settings_menu,
    tasks_menu,
)
from bot.ui.messages import HELP, MENU_NOTES, MENU_SCHEDULE, MENU_SETTINGS, MENU_TASKS, START


def _reset_state(user: str) -> None:
    session = storage.get_session(user)
    if session.state == SessionState.IDLE:
        return
    session.state = SessionState.IDLE
    session.subject = None
    session.lesson_type = None
    session.status_message_id = None
    storage.save_session(session)


async def show_root(event) -> None:
    _reset_state(user_id(event))
    await event.bot.send_message(chat_id=chat_id(event), text=START, attachments=[main_menu()])


async def show_help(event) -> None:
    await event.bot.send_message(chat_id=chat_id(event), text=HELP, attachments=[help_menu()])


async def route(event, payload: str) -> None:
    kind = payload.split(":", 1)[1]
    chat = chat_id(event)
    user = user_id(event)
    if kind == "root":
        _reset_state(user)
        await event.bot.send_message(chat_id=chat, text=START, attachments=[main_menu()])
    elif kind == "notes":
        _reset_state(user)
        await event.bot.send_message(chat_id=chat, text=MENU_NOTES, attachments=[notes_menu(False)])
    elif kind == "schedule":
        _reset_state(user)
        await event.bot.send_message(chat_id=chat, text=MENU_SCHEDULE, attachments=[schedule_menu()])
    elif kind == "tasks":
        _reset_state(user)
        await event.bot.send_message(chat_id=chat, text=MENU_TASKS, attachments=[tasks_menu()])
    elif kind == "settings":
        _reset_state(user)
        await event.bot.send_message(chat_id=chat, text=MENU_SETTINGS, attachments=[settings_menu()])
    elif kind == "help":
        await show_help(event)

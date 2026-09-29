"""
    Desc: single router for all bot events
    Creator: Kirosha
"""

from __future__ import annotations

from maxapi.types import Command, MessageCallback, MessageCreated

from based.utils.__console import log_step

from bot.config import config
from bot.handlers import (
    __conspect,
    __help,
    __menu,
    __schedule,
    __settings,
    __tasks,
)
from bot.security import rate_limiter
from bot.session.state import SessionState
from bot.session.storage import storage
from bot.ui import chat_id as extract_chat
from bot.ui import user_id as extract_user
from bot.ui.messages import MESSAGE_TOO_LONG
from bot.utils.__errors import report


def save_chat_id(event) -> None:
    try:
        chat = extract_chat(event)
    except Exception:
        return
    user = extract_user(event)
    if not user or not chat:
        return
    storage.set_user_setting(user, "chat_id", str(chat))


def reset_session_state(user: str) -> None:
    session = storage.get_session(user)
    if session.state == SessionState.IDLE:
        return
    session.state = SessionState.IDLE
    session.subject = None
    session.lesson_type = None
    session.status_message_id = None
    storage.save_session(session)


def register(dp) -> None:
    @dp.message_created(Command("start"))
    async def start(event: MessageCreated) -> None:
        user = extract_user(event)
        log_step(f"[bot] user={user} action=start")
        save_chat_id(event)
        reset_session_state(user)
        try:
            await __menu.show_root(event)
        except Exception as err:
            await report(event, "start", err)

    @dp.message_created(Command("help"))
    async def help_command(event: MessageCreated) -> None:
        log_step(f"[bot] user={extract_user(event)} action=help")
        save_chat_id(event)
        try:
            await __menu.show_help(event)
        except Exception as err:
            await report(event, "help", err)

    @dp.message_created(Command("cancel"))
    async def cancel_command(event: MessageCreated) -> None:
        log_step(f"[bot] user={extract_user(event)} action=cancel")
        save_chat_id(event)
        try:
            await __conspect.cancel_session(event)
        except Exception as err:
            await report(event, "cancel", err)

    @dp.message_callback()
    async def on_callback(event: MessageCallback) -> None:
        payload = event.callback.payload or ""
        user = extract_user(event)
        ok, reason = rate_limiter.check(user)
        if not ok:
            try:
                await event.bot.send_message(chat_id=extract_chat(event), text=reason)
            except Exception:
                pass
            return
        log_step(f"[bot] user={user} action=callback payload={payload}")
        save_chat_id(event)
        try:
            if payload.startswith("menu:"):
                await __menu.route(event, payload)
            elif payload.startswith("notes:"):
                await __conspect.route(event, payload)
            elif payload.startswith("schedule:"):
                await __schedule.route(event, payload)
            elif payload.startswith("tasks:"):
                await __tasks.route(event, payload)
            elif payload.startswith("settings:"):
                await __settings.route(event, payload)
            elif payload.startswith("notif:"):
                await __settings.handle_notif(event, payload)
            elif payload.startswith("help:"):
                await __help.route(event, payload)
        except Exception as err:
            await report(event, f"callback:{payload}", err)

    @dp.message_created()
    async def on_message(event: MessageCreated) -> None:
        body = event.message.body
        if body is None:
            return
        user = extract_user(event)
        text = (body.text or "").strip() if body.text else ""
        ok, reason = rate_limiter.check(user)
        if not ok:
            try:
                await event.bot.send_message(chat_id=extract_chat(event), text=reason)
            except Exception:
                pass
            return
        if text and len(text) > config.max_text_length:
            try:
                await event.bot.send_message(
                    chat_id=extract_chat(event),
                    text=MESSAGE_TOO_LONG.format(length=len(text), limit=config.max_text_length),
                )
            except Exception:
                pass
            return
        log_step(f"[bot] user={user} action=message text={text[:40]!r} files={len(body.attachments or [])}")
        save_chat_id(event)
        try:
            if await __conspect.handle_message(event, text, body.attachments or []):
                return
            if await __settings.handle_notif_input(event, text):
                return
            if await __schedule.handle_message(event, body.attachments or []):
                return
            if await __tasks.handle_message(event, text):
                return
        except Exception as err:
            await report(event, "message", err)

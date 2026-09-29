"""
    Desc: /help_notes, /help_skeds, /help_tasks handlers
    Creator: Kirosha
"""

from __future__ import annotations

from maxapi.types import Command, MessageCreated

from bot.ui import chat_id
from bot.ui.keyboards import help_menu
from bot.ui.messages import HELP, HELP_NOTES, HELP_SKEDS, HELP_TASKS


async def route(event, payload: str) -> None:
    target = payload.split(":", 1)[1]
    text = {
        "notes": HELP_NOTES,
        "skeds": HELP_SKEDS,
        "tasks": HELP_TASKS,
    }.get(target, HELP)
    await event.bot.send_message(
        chat_id=chat_id(event), text=text, attachments=[help_menu()]
    )


def register(dp) -> None:
    @dp.message_created(Command("help_notes"))
    async def help_notes(event: MessageCreated) -> None:
        await event.bot.send_message(
            chat_id=chat_id(event), text=HELP_NOTES, attachments=[help_menu()]
        )

    @dp.message_created(Command("help_skeds"))
    async def help_skeds(event: MessageCreated) -> None:
        await event.bot.send_message(
            chat_id=chat_id(event), text=HELP_SKEDS, attachments=[help_menu()]
        )

    @dp.message_created(Command("help_tasks"))
    async def help_tasks(event: MessageCreated) -> None:
        await event.bot.send_message(
            chat_id=chat_id(event), text=HELP_TASKS, attachments=[help_menu()]
        )

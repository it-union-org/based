"""
    Desc: helpers for safe message deletion and short-lived notices
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio

from bot.ui import chat_id
from based.utils.__console import log_warn


async def safe_delete(event, message_id) -> bool:
    try:
        await event.bot.delete_message(message_id=str(message_id))
        return True
    except Exception as err:
        log_warn(f"bot delete failed id={message_id}: {err.__class__.__name__}: {err}")
        return False


async def delete_user_message(event) -> bool:
    body = getattr(getattr(event, "message", None), "body", None)
    if body is None:
        return False
    return await safe_delete(event, body.mid)


async def send_temp(event, text: str, seconds: int = 5) -> None:
    message = await event.bot.send_message(chat_id=chat_id(event), text=text)
    message_id = getattr(message, "message_id", None)
    if message_id is None:
        return

    async def cleanup() -> None:
        await asyncio.sleep(seconds)
        try:
            await event.bot.delete_message(message_id=str(message_id))
        except Exception:
            pass

    asyncio.create_task(cleanup())

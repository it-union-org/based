"""
    Desc: unified error logging and user-facing error reporting
    Creator: Kirosha
"""

from __future__ import annotations

import traceback

from based.utils.__console import log_err

from bot.ui import chat_id
from bot.ui.keyboards import error_keyboard
from bot.ui.messages import ERROR_MESSAGE


def user_id(event) -> str:
    user = getattr(event, "from_user", None)
    return str(getattr(user, "user_id", "unknown")) if user else "unknown"


async def report(event, action: str, err: Exception) -> None:
    uid = user_id(event)
    reason = f"{err.__class__.__name__}: {err}"
    log_err(f"[bot] user={uid} action={action} reason={reason}")
    traceback.print_exc()
    detail = short_detail(err)
    full = full_detail(action, uid, err)
    try:
        await event.bot.send_message(
            chat_id=chat_id(event),
            text=ERROR_MESSAGE.format(short=detail, details=full[:1500]),
            attachments=[error_keyboard(full)],
        )
    except Exception:
        pass


def short_detail(err: Exception) -> str:
    text = str(err).strip() or err.__class__.__name__
    return text[:200]


def full_detail(action: str, user_id: str, err: Exception) -> str:
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    return f"action: {action}\nuser: {user_id}\n\n{tb}"

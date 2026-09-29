"""
    Desc: shared helpers for bot UI
    Creator: Kirosha
"""

from __future__ import annotations


def chat_id(event) -> int:
    direct = getattr(event, "chat_id", None)
    if direct:
        return int(direct)
    message = getattr(event, "message", None)
    if message is not None:
        recipient = getattr(message, "recipient", None)
        if recipient is not None:
            rid = getattr(recipient, "chat_id", None)
            if rid:
                return int(rid)
        body = getattr(message, "body", None)
        if body is not None:
            bid = getattr(body, "chat_id", None)
            if bid:
                return int(bid)
    raise RuntimeError("cannot determine chat_id from event")


def user_id(event) -> str:
    user = getattr(event, "from_user", None)
    if user is not None:
        return str(getattr(user, "user_id", ""))
    return ""

"""
    Desc: tasks flow with three statuses and hard delete
    Creator: Kirosha
"""

from __future__ import annotations

from maxapi.types import ButtonsPayload, CallbackButton

from based.modules.tasks.api import TasksAPI
from based.modules.tasks.schemas import TaskStatus

from bot.session.state import SessionState
from bot.session.storage import storage
from bot.ui import chat_id
from bot.ui.keyboards import tasks_menu
from bot.ui.messages import (
    TASK_ADD_BAD_FORMAT,
    TASK_ADD_DONE,
    TASK_ADD_PROMPT,
    TASK_EDIT_FAILED,
    TASK_ITEM,
    TASKS_EMPTY,
    TASKS_HEADER,
)

from based.utils.__console import log_warn


def pack(rows) -> ButtonsPayload:
    return ButtonsPayload(buttons=rows).pack()


def cb(text: str, payload: str) -> CallbackButton:
    return CallbackButton(text=text, payload=payload)


def mark(status: TaskStatus) -> str:
    if status == TaskStatus.DONE:
        return "✅"
    if status == TaskStatus.CANCELLED:
        return "❌"
    return "⏳"


def build_text(tasks) -> str:
    if not tasks:
        return TASKS_EMPTY
    lines = [TASKS_HEADER]
    for task in tasks:
        lines.append(
            TASK_ITEM.format(
                mark=mark(task.status),
                number=task.task_number,
                subject=task.subject,
                description=task.description[:60],
            )
        )
    return "\n".join(lines)


def actions(task) -> list:
    n = task.task_number
    if task.status == TaskStatus.PENDING:
        return [
            cb(f"✅ {n}", f"tasks:done:{n}"),
            cb(f"❌ {n}", f"tasks:cancel:{n}"),
            cb(f"🗑 {n}", f"tasks:delete:{n}"),
        ]
    return [
        cb(f"↩ {n}", f"tasks:reopen:{n}"),
        cb(f"🗑 {n}", f"tasks:delete:{n}"),
    ]


def build_keyboard(tasks) -> ButtonsPayload:
    rows = [actions(task) for task in tasks]
    rows.append([cb("Назад", "menu:tasks")])
    return pack(rows)


async def route(event, payload: str) -> None:
    action = payload.split(":", 1)[1]
    if action.startswith("list"):
        parts = action.split(":", 1)
        filter_key = parts[1] if len(parts) > 1 else "pending"
        await show(event, filter_key, edit=False)
    elif action == "add":
        user = str(event.from_user.user_id)
        session = storage.get_session(user)
        session.state = SessionState.AWAITING_TASK_ADD
        storage.save_session(session)
        await event.bot.send_message(
            chat_id=chat_id(event),
            text=TASK_ADD_PROMPT,
            attachments=[tasks_menu()],
        )
    elif action.startswith("done:"):
        await act(event, action, "done")
    elif action.startswith("cancel:"):
        await act(event, action, "cancel")
    elif action.startswith("reopen:"):
        await act(event, action, "reopen")
    elif action.startswith("delete:"):
        await act(event, action, "delete")


async def act(event, action: str, kind: str) -> None:
    user = str(event.from_user.user_id)
    number = int(action.split(":")[-1])
    api = TasksAPI()
    if kind == "done":
        api.mark_done(user, number)
    elif kind == "cancel":
        api.mark_cancelled(user, number)
    elif kind == "reopen":
        api.mark_pending(user, number)
    elif kind == "delete":
        api.hard_delete(user, number)
    await show(event, "pending", edit=True)


async def show(event, filter_key: str, edit: bool = False) -> None:
    user = str(event.from_user.user_id)
    api = TasksAPI()
    if filter_key == "all":
        tasks = api.list(user)
    elif filter_key == "done":
        tasks = api.list(user, status=TaskStatus.DONE.value)
    elif filter_key == "cancelled":
        tasks = api.list(user, status=TaskStatus.CANCELLED.value)
    else:
        tasks = api.list(user, status=TaskStatus.PENDING.value)

    body = build_text(tasks)
    keyboard = build_keyboard(tasks)
    chat = chat_id(event)

    if edit:
        try:
            await event.bot.edit_message(
                message_id=str(event.message.body.mid),
                text=body,
                attachments=[keyboard],
            )
            return
        except Exception as err:
            log_warn(TASK_EDIT_FAILED.format(error=f"{err.__class__.__name__}: {err}"))

    await event.bot.send_message(chat_id=chat, text=body, attachments=[keyboard])


async def handle_message(event, text: str) -> bool:
    user = str(event.from_user.user_id)
    chat = chat_id(event)
    session = storage.get_session(user)

    if session.state != SessionState.AWAITING_TASK_ADD:
        return False

    if not text or "|" not in text:
        return False

    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await event.bot.send_message(chat_id=chat, text=TASK_ADD_BAD_FORMAT)
        return True

    subject, due_date, description = parts[0], parts[1], "|".join(parts[2:])
    try:
        await event.bot.delete_message(message_id=str(event.message.body.mid))
    except Exception:
        pass

    try:
        TasksAPI().add(
            user_id=user,
            subject=subject,
            due_date=due_date,
            description=description,
        )
        session.state = SessionState.IDLE
        storage.save_session(session)
        await event.bot.send_message(
            chat_id=chat,
            text=TASK_ADD_DONE.format(subject=subject, due_date=due_date),
            attachments=[tasks_menu()],
        )
    except Exception as err:
        await event.bot.send_message(chat_id=chat, text=f"{err.__class__.__name__}: {err}")
    return True

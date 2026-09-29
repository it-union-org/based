"""
    Desc: schedule flow: today, tomorrow, week, upload
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from based.utils.__console import log_warn
from bot.session.files import attachment_name, attachment_url, save_bytes
from bot.session.state import SessionState
from bot.session.storage import storage
from bot.ui import chat_id
from bot.ui.__messages import safe_delete
from bot.ui.keyboards import schedule_menu
from bot.ui.messages import (
    PROCESSING_SCHEDULE_FILE,
    SCHEDULE_EMPTY,
    SCHEDULE_NO_GROUP,
    SCHEDULE_PARSE_FAILED,
    SCHEDULE_UPLOAD_DONE,
    SCHEDULE_UPLOAD_PROMPT,
)
from bot.utils.__errors import report


async def route(event, payload: str) -> None:
    action = payload.split(":", 1)[1]
    if action == "today":
        await day(event, 0)
    elif action == "tomorrow":
        await day(event, 1)
    elif action == "week":
        await week(event)
    elif action == "upload":
        await start_upload(event)


async def start_upload(event) -> None:
    user = str(event.from_user.user_id)
    session = storage.get_session(user)
    session.state = SessionState.AWAITING_SCHEDULE_FILE
    storage.save_session(session)
    await event.bot.send_message(
        chat_id=chat_id(event),
        text=SCHEDULE_UPLOAD_PROMPT,
        attachments=[schedule_menu()],
    )


async def day(event, offset_days: int) -> None:
    chat = chat_id(event)
    user = str(event.from_user.user_id)
    settings = storage.get_user_settings(user)
    group_name = settings.get("group_name")
    if not group_name:
        await event.bot.send_message(
            chat_id=chat, text=SCHEDULE_NO_GROUP, attachments=[schedule_menu()]
        )
        return

    from based.modules.skeds.api import SkedsAPI
    from based.utils.__db import get_db

    api = SkedsAPI()
    target = (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")
    lessons = api.get_day(group_name, target)
    if not lessons:
        lessons = api.get_day_all(target)

    shifted = False
    if not lessons:
        min_date = get_db().min_lesson_date_all()
        if min_date and min_date > target:
            candidate = api.get_day_all(min_date)
            if candidate:
                lessons = candidate
                target = min_date
                shifted = True

    if not lessons:
        await event.bot.send_message(
            chat_id=chat,
            text=SCHEDULE_EMPTY.format(date=target),
            attachments=[schedule_menu()],
        )
        return

    header = day_header(offset_days, target)
    if shifted:
        header = f"(сегодня занятий нет, ближайшая дата)\n{header}"
    lines = [header]
    for lesson in lessons:
        lines.append(lesson_block(lesson))
    await event.bot.send_message(
        chat_id=chat, text="\n".join(lines), attachments=[schedule_menu()]
    )


def day_header(offset: int, date: str) -> str:
    if offset == 0:
        return f"📅 Сегодня, {date}"
    if offset == 1:
        return f"📅 Завтра, {date}"
    return f"📅 {date}"


def lesson_block(lesson: dict) -> str:
    start = lesson["start_time"]
    end = lesson["end_time"]
    subject = lesson["subject"]
    teacher = lesson.get("teacher") or "—"
    room = lesson.get("room") or "—"
    kind = lesson.get("lesson_type") or ""
    marker = status_marker(start, end)
    header = f"{marker} {start}–{end}" if marker else f"🕐 {start}–{end}"
    block = (
        f"\n{header}\n"
        f"   📚 {subject}\n"
        f"   👤 {teacher}\n"
        f"   🚪 ауд. {room}"
    )
    if kind:
        block += f"\n   📌 {kind}"
    return block


def status_marker(start: str, end: str) -> str:
    now = datetime.now().strftime("%H:%M")
    if start <= now < end:
        return "🟢"
    return ""


async def week(event) -> None:
    chat = chat_id(event)
    user = str(event.from_user.user_id)
    settings = storage.get_user_settings(user)
    group_name = settings.get("group_name")
    if not group_name:
        await event.bot.send_message(
            chat_id=chat, text=SCHEDULE_NO_GROUP, attachments=[schedule_menu()]
        )
        return

    from based.modules.skeds.api import SkedsAPI
    from based.utils.__db import get_db

    api = SkedsAPI()
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    min_date = get_db().min_lesson_date_all() or get_db().min_lesson_date(group_name)
    start = today_str
    if min_date and min_date > today_str:
        start = min_date

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end = (start_dt + timedelta(days=6)).strftime("%Y-%m-%d")
    lessons = api.get_range(group_name, start, end)
    if not lessons:
        lessons = api.get_range_all(start, end)
    if not lessons:
        await event.bot.send_message(
            chat_id=chat,
            text=SCHEDULE_EMPTY.format(date=start),
            attachments=[schedule_menu()],
        )
        return
    lines = [f"📅 Расписание на неделю, с {start}:"]
    current_date = None
    for lesson in lessons:
        if lesson["date"] != current_date:
            current_date = lesson["date"]
            lines.append(f"\n🗓 {current_date}")
        lines.append(lesson_block(lesson))
    await event.bot.send_message(
        chat_id=chat, text="\n".join(lines), attachments=[schedule_menu()]
    )


async def handle_message(event, attachments: list) -> bool:
    if not attachments:
        return False
    user = str(event.from_user.user_id)
    chat = chat_id(event)
    session = storage.get_session(user)

    if session.state != SessionState.AWAITING_SCHEDULE_FILE:
        return False

    attachment = attachments[0]
    url = attachment_url(attachment)
    if not url:
        return False

    progress = await event.bot.send_message(
        chat_id=chat, text=PROCESSING_SCHEDULE_FILE
    )
    progress_id = getattr(progress, "message_id", None)

    async def on_progress(text: str) -> None:
        if progress_id is None:
            return
        try:
            await event.bot.edit_message(message_id=str(progress_id), text=f"⏳ {text}")
        except Exception:
            pass

    try:
        import httpx

        from bot.config import config as bot_config

        data = None
        last_error = None
        for attempt in range(1, 5):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.content
                break
            except httpx.HTTPStatusError as err:
                last_error = f"HTTP {err.response.status_code}"
                log_warn(f"schedule download attempt {attempt}/4: {last_error}")
                await asyncio.sleep(2 * attempt)
            except httpx.RequestError as err:
                last_error = f"{err.__class__.__name__}: {err}"
                log_warn(f"schedule download attempt {attempt}/4: {last_error}")
                await asyncio.sleep(2 * attempt)

        if data is None:
            await event.bot.send_message(
                chat_id=chat,
                text=f"Не удалось скачать файл: {last_error}. "
                     f"Попробуй ещё раз через минуту.",
                attachments=[schedule_menu()],
            )
            return True

        if len(data) > bot_config.max_file_size_mb * 1024 * 1024:
            await event.bot.send_message(
                chat_id=chat,
                text=f"Файл слишком большой ({len(data) / 1024 / 1024:.1f} МБ). "
                     f"Лимит: {bot_config.max_file_size_mb} МБ.",
            )
            return True

        base_name = attachment_name(attachment, fallback="schedule")
        file = save_bytes(user, str(base_name), data)

        from based.modules.skeds.api import SkedsAPI

        api = SkedsAPI()
        schedule = await api.parse(
            Path(file.local_path),
            group_name=f"user_{user}",
            progress_cb=on_progress,
        )

        if progress_id:
            await safe_delete(event, progress_id)

        if schedule is None:
            await event.bot.send_message(
                chat_id=chat, text=SCHEDULE_PARSE_FAILED, attachments=[schedule_menu()]
            )
        else:
            storage.set_user_setting(user, "group_name", schedule.group_name)
            await event.bot.send_message(
                chat_id=chat,
                text=SCHEDULE_UPLOAD_DONE.format(
                    lessons=len(schedule.lessons),
                    from_date=schedule.from_date,
                    to_date=schedule.to_date,
                ),
                attachments=[schedule_menu()],
            )
    except Exception as err:
        if progress_id:
            await safe_delete(event, progress_id)
        await report(event, "schedule:upload", err)
    finally:
        session = storage.get_session(user)
        session.state = SessionState.IDLE
        storage.save_session(session)

    return True

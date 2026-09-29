"""
    Desc: notes flow: material upload, generation, cancel
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio

from datetime import datetime
from pathlib import Path

from bot.config import config
from bot.security import extension_ok
from bot.session.files import clear_session_files, save_bytes, total_size_bytes
from bot.session.state import LESSON_TYPES, SessionState
from bot.session.storage import storage
from bot.ui import chat_id
from bot.ui.__messages import safe_delete, send_temp
from bot.utils.__pdf import md_to_pdf, upload_file, send_file as send_pdf_file
from bot.ui.keyboards import (
    collecting_keyboard,
    lesson_type_keyboard,
    main_menu,
    notes_menu,
)
from bot.ui.messages import (
    AWAITING_SUBJECT,
    AWAITING_TYPE,
    CANCELLED,
    COLLECTING_HEADER,
    DONE,
    DONE_FOOTER,
    FILE_FAILED,
    FILE_LIMIT,
    NO_MATERIALS,
    NO_NOTE_CREATED,
    PROCESSING_START,
    WHAT_NEXT,
)
from bot.utils.__errors import report
from based.utils.__console import log_warn


def collecting_text(session) -> str:
    return COLLECTING_HEADER.format(
        audio=session.count("audio"),
        images=session.count("image"),
        presentations=session.count("presentation"),
        texts=session.count("text"),
    )


async def edit_status(event, session, chat: int) -> None:
    text = collecting_text(session)
    keyboard = collecting_keyboard()
    if session.status_message_id:
        try:
            await event.bot.edit_message(
                message_id=str(session.status_message_id),
                text=text,
                attachments=[keyboard],
            )
            return
        except Exception as err:
            log_warn(f"bot edit_message failed: {err.__class__.__name__}: {err}")
    message = await event.bot.send_message(
        chat_id=chat,
        text=text,
        attachments=[keyboard],
    )
    session.status_message_id = str(getattr(message, "message_id", ""))
    storage.save_session(session)


def _set_state(user: str, state: SessionState, subject: str | None = None, lesson_type: str | None = None) -> None:
    session = storage.get_session(user)
    session.state = state
    if subject is not None:
        session.subject = subject
    if lesson_type is not None:
        session.lesson_type = lesson_type
    storage.save_session(session)


async def route(event, payload: str) -> None:
    chat = chat_id(event)
    user = str(event.from_user.user_id)
    action = payload.split(":", 1)[1]

    if action == "upload":
        await start_upload(event, user, chat)
    elif action.startswith("type:"):
        lesson_type = action.split(":", 1)[1]
        await set_type(event, user, chat, lesson_type)
    elif action == "back_to_subject":
        _set_state(user, SessionState.AWAITING_SUBJECT)
        await event.bot.send_message(chat_id=chat, text=AWAITING_SUBJECT)
    elif action == "generate":
        await generate(event, user, chat)


async def start_upload(event, user: str, chat: int) -> None:
    session = storage.get_session(user)
    if session.status_message_id:
        await safe_delete(event, session.status_message_id)
    session.state = SessionState.AWAITING_SUBJECT
    session.subject = None
    session.lesson_type = None
    session.status_message_id = None
    clear_session_files(user)
    storage.clear_files(user)
    storage.save_session(session)
    await event.bot.send_message(chat_id=chat, text=AWAITING_SUBJECT)


async def set_type(event, user: str, chat: int, lesson_type: str) -> None:
    if lesson_type not in LESSON_TYPES:
        lesson_type = "другое"
    session = storage.get_session(user)
    session.lesson_type = lesson_type
    session.state = SessionState.COLLECTING_FILES
    storage.save_session(session)
    await edit_status(event, session, chat)


async def handle_message(event, text: str, attachments: list) -> bool:
    user = str(event.from_user.user_id)
    chat = chat_id(event)
    session = storage.get_session(user)

    if session.state == SessionState.AWAITING_SUBJECT and text:
        session.subject = text[:200]
        session.state = SessionState.AWAITING_TYPE
        storage.save_session(session)
        await event.bot.send_message(
            chat_id=chat,
            text=AWAITING_TYPE,
            attachments=[lesson_type_keyboard()],
        )
        return True

    if session.state == SessionState.COLLECTING_FILES and attachments:
        for attachment in attachments:
            await save_attachment(event, session, attachment, chat)
        session = storage.get_session(user)
        await edit_status(event, session, chat)
        return True

    return False


async def save_attachment(event, session, attachment, chat: int) -> bool:
    user = session.user_id
    if len(session.files) >= config.max_files_per_session:
        await event.bot.send_message(
            chat_id=chat,
            text=FILE_LIMIT.format(limit=config.max_files_per_session),
        )
        return False
    try:
        from bot.session.files import attachment_url, attachment_name

        url = attachment_url(attachment)
        if not url:
            return False

        import httpx

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
                log_warn(f"bot download attempt {attempt}/4: {last_error}")
                await asyncio.sleep(2 * attempt)
            except httpx.RequestError as err:
                last_error = f"{err.__class__.__name__}: {err}"
                log_warn(f"bot download attempt {attempt}/4: {last_error}")
                await asyncio.sleep(2 * attempt)

        if data is None:
            await event.bot.send_message(
                chat_id=chat,
                text=f"Не удалось скачать файл: {last_error}. Попробуй ещё раз.",
            )
            return False

        if len(data) > config.max_file_size_mb * 1024 * 1024:
            await event.bot.send_message(
                chat_id=chat,
                text=f"Файл слишком большой ({len(data) / 1024 / 1024:.1f} МБ). "
                     f"Лимит: {config.max_file_size_mb} МБ.",
            )
            return False

        current = total_size_bytes(user)
        if current + len(data) > config.max_total_size_mb * 1024 * 1024:
            await event.bot.send_message(
                chat_id=chat,
                text=f"Превышен общий лимит сессии ({config.max_total_size_mb} МБ).",
            )
            return False

        base_name = attachment_name(attachment, fallback="file")
        ok, reason = extension_ok(str(base_name))
        if not ok:
            await event.bot.send_message(chat_id=chat, text=reason)
            return False
        file = save_bytes(user, str(base_name), data)
        storage.add_file(user, file)
        log_warn(f"bot saved {file.file_type}: {file.local_path} ({file.size_bytes} bytes)")
        return True
    except Exception as err:
        await event.bot.send_message(
            chat_id=chat,
            text=FILE_FAILED.format(
                name=str(getattr(attachment, "type", "файл")),
                reason=f"{err.__class__.__name__}: {err}",
                audio=session.count("audio"),
                images=session.count("image"),
                presentations=session.count("presentation"),
                texts=session.count("text"),
            ),
        )
        return False


async def generate(event, user: str, chat: int) -> None:
    session = storage.get_session(user)
    if not session.files:
        await event.bot.send_message(
            chat_id=chat,
            text=NO_MATERIALS,
            attachments=[notes_menu(False)],
        )
        return

    if session.status_message_id:
        await safe_delete(event, session.status_message_id)

    progress = await event.bot.send_message(chat_id=chat, text=PROCESSING_START)
    progress_id = getattr(progress, "message_id", None)
    stage = {"text": PROCESSING_START}

    async def on_progress(text: str) -> None:
        stage["text"] = f"⏳ {text}"
        if progress_id is None:
            return
        try:
            await event.bot.edit_message(message_id=str(progress_id), text=stage["text"])
        except Exception:
            pass

    async def progress_timer() -> None:
        import asyncio
        import time

        started = time.monotonic()
        while True:
            await asyncio.sleep(5)
            if progress_id is None:
                return
            elapsed = int(time.monotonic() - started)
            try:
                await event.bot.edit_message(
                    message_id=str(progress_id),
                    text=f"{stage['text']} ({elapsed} сек)",
                )
            except Exception:
                return

    import asyncio

    timer_task = asyncio.create_task(progress_timer())

    try:
        note_path = await run_pipeline(session, on_progress)
    except Exception as err:
        timer_task.cancel()
        if progress_id:
            await safe_delete(event, progress_id)
        await report(event, "notes:generate", err)
        return

    timer_task.cancel()

    if progress_id:
        await safe_delete(event, progress_id)

    if note_path is None:
        await event.bot.send_message(
            chat_id=chat,
            text=NO_NOTE_CREATED,
            attachments=[main_menu()],
        )
        return

    caption = DONE.format(
        subject=session.subject or "Без названия",
        lesson_type=session.lesson_type or "не указан",
        date=datetime.now().strftime("%d.%m.%Y, %H:%M"),
    )
    pdf_ok = await send_note_pdf(event, chat, note_path, caption)
    if not pdf_ok:
        body = note_path.read_text(encoding="utf-8")
        preview = f"{caption}\n\n{body[:800]}"
        await event.bot.send_message(chat_id=chat, text=preview)

    clear_session_files(user)
    storage.clear_files(user)
    cleanup_note_dir(note_path)

    session.state = SessionState.IDLE
    session.subject = None
    session.lesson_type = None
    session.status_message_id = None
    storage.save_session(session)

    await event.bot.send_message(
        chat_id=chat,
        text=DONE_FOOTER,
        attachments=[main_menu()],
    )


async def run_pipeline(session, on_progress) -> Path | None:
    from based.modules.notes.api import NotesAPI, NoteRequest

    audio = [Path(f.local_path) for f in session.files if f.file_type == "audio"]
    images = [Path(f.local_path) for f in session.files if f.file_type == "image"]
    presentations = [Path(f.local_path) for f in session.files if f.file_type == "presentation"]
    texts = [
        Path(f.local_path).read_text(encoding="utf-8")
        for f in session.files
        if f.file_type == "text"
    ]

    api = NotesAPI()
    request = NoteRequest(
        audio_paths=audio,
        image_paths=images,
        presentation_path=presentations[0] if presentations else None,
        raw_text="\n\n".join(texts) if texts else None,
        subject_name=session.subject or "Лекция",
    )
    return await api.create_note(request, progress_cb=on_progress)



async def send_note_pdf(event, chat: int, note_path: Path, caption: str) -> bool:
    """Конвертирует note.md в PDF и отправляет файлом."""
    from bot.config import config as bot_config
    import asyncio

    pdf_path = note_path.with_suffix(".pdf")
    try:
        ok = await asyncio.to_thread(md_to_pdf, note_path, pdf_path)
    except Exception as err:
        log_warn(f"pdf conversion failed: {err.__class__.__name__}: {err}")
        return False
    if not ok:
        log_warn("pdf conversion returned False")
        return False

    try:
        file_token = await upload_file(bot_config.token, pdf_path, "file")
    except Exception as err:
        log_warn(f"pdf upload failed: {err.__class__.__name__}: {err}")
        return False
    if not file_token:
        return False

    user_id = str(event.from_user.user_id)
    try:
        return await send_pdf_file(bot_config.token, user_id, file_token, caption)
    except Exception as err:
        log_warn(f"pdf send failed: {err.__class__.__name__}: {err}")
        return False

def cleanup_note_dir(note_path: Path) -> None:
    import shutil

    parent = note_path.parent
    if "cache" in str(parent) and parent.name:
        shutil.rmtree(parent, ignore_errors=True)


async def cancel_session(event) -> None:
    user = str(event.from_user.user_id)
    chat = chat_id(event)
    session = storage.get_session(user)
    if session.status_message_id:
        await safe_delete(event, session.status_message_id)
    clear_session_files(user)
    storage.clear_files(user)
    session.state = SessionState.IDLE
    session.subject = None
    session.lesson_type = None
    session.status_message_id = None
    storage.save_session(session)
    await send_temp(event, CANCELLED, seconds=5)
    await event.bot.send_message(
        chat_id=chat,
        text=WHAT_NEXT,
        attachments=[main_menu()],
    )

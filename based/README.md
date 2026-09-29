# based — API

Справочник по публичным интерфейсам библиотеки. Для обзора проекта — [../README.md](../README.md).

## based

### BasedAPI

```python
from based import BasedAPI

api = BasedAPI()
```

| Метод | Описание |
|---|---|
| `load(skip_setup: bool = False) -> None` | скачивает ассеты, проверяет модули, регистрирует API |
| `health() -> dict` | снапшот состояния всех модулей |
| `timings() -> dict` | метрики времени по стадиям загрузки |
| `close() -> None` | очищает модули и метрики |

После `load()` доступны атрибуты:

- `api.notes` — `NotesAPI`
- `api.skeds` — `SkedsAPI`
- `api.tasks` — `TasksAPI`
- `api.modules: dict[str, object]`
- `api.failed: dict[str, str]`
- `api.metrics: dict`

### Метрики

`timings()` возвращает:

```python
{
    "total_seconds": 849.282,
    "assets_seconds": 0.0,
    "modules": {
        "notes": {
            "status": "ok",
            "verify_seconds": 0.0,
            "setup_seconds": 0.0,
            "test_seconds": 809.703,
            "instantiate_seconds": 0.0,
            "total_seconds": 809.735,
        },
        ...
    }
}
```

## notes

### NotesAPI

```python
from based.modules.notes.api import NotesAPI, NoteRequest

api = NotesAPI()
```

| Метод | Описание |
|---|---|
| `async create_note(request: NoteRequest, progress_cb=None) -> Path \| None` | полный пайплайн, возвращает путь к `note.md` |
| `async create_note_from_text(text: str, subject_name: str, progress_cb=None) -> Path \| None` | конспект из текста |
| `health_check() -> dict` | снапшот состояния |

### NoteRequest

```python
from pathlib import Path
from based.modules.notes.schemas import NoteRequest

NoteRequest(
    audio_paths=[Path("lecture.m4a")],
    image_paths=[Path("board.jpg")],
    presentation_path=Path("slides.pdf") | None,
    raw_text="..." | None,
    subject_name="Математический анализ",
)
```

`progress_cb: Callable[[str], Awaitable[None]]` — колбэк с текстом этапа.

## skeds

### SkedsAPI

```python
from based.modules.skeds.api import SkedsAPI

api = SkedsAPI()
```

| Метод | Описание |
|---|---|
| `async parse(source: Path, group_name=None, progress_cb=None) -> Schedule \| None` | парсит файл и сохраняет в SQLite |
| `get_day(group_name: str, date: str) -> list[dict]` | занятия на дату |
| `get_range(group_name: str, from_date: str, to_date: str) -> list[dict]` | занятия за период |
| `get_day_all(date: str) -> list[dict]` | занятия на дату без фильтра по группе |
| `get_range_all(from_date: str, to_date: str) -> list[dict]` | занятия за период без фильтра |
| `health_check() -> dict` | снапшот состояния |

### Схемы

```python
from based.modules.skeds.schemas import Schedule, Lesson, ScheduleRequest

Schedule(
    group_name: str,
    from_date: str,          # YYYY-MM-DD
    to_date: str,            # YYYY-MM-DD
    source: str,
    lessons: list[Lesson],
    parsed_at: str,          # ISO 8601
)

Lesson(
    id: str,
    group_name: str | None,
    subject: str,
    teacher: str | None,
    room: str | None,
    address: str | None,
    date: str,               # YYYY-MM-DD
    start_time: str,         # HH:MM
    end_time: str,           # HH:MM
    lesson_type: str | None,
    raw_type: str | None,
    subgroup: str | None,
    link: str | None,
)
```

## tasks

### TasksAPI

```python
from based.modules.tasks.api import TasksAPI

api = TasksAPI()
```

| Метод | Описание |
|---|---|
| `add(user_id, subject, due_date, description, lesson_date=None) -> Task` | добавить задачу |
| `get(user_id, task_number) -> Task \| None` | одна задача |
| `list(user_id, status=None, due_date=None) -> list[Task]` | список с фильтрами |
| `today(user_id) -> list[Task]` | задачи на сегодня |
| `tomorrow(user_id) -> list[Task]` | задачи на завтра |
| `week(user_id) -> list[Task]` | задачи на 7 дней |
| `mark_done(user_id, task_number) -> None` | отметить выполненной |
| `mark_cancelled(user_id, task_number) -> None` | отменить |
| `mark_pending(user_id, task_number) -> None` | вернуть в работу |
| `hard_delete(user_id, task_number) -> int` | удалить из БД |
| `cancel_for_lesson(user_id, subject, lesson_date) -> int` | массовая отмена |
| `subjects(user_id) -> list[str]` | предметы из расписания группы |
| `health_check() -> dict` | снапшот состояния |

### Схема

```python
from based.modules.tasks.schemas import Task, TaskStatus

Task(
    user_id: str,
    task_number: int,
    subject: str,
    due_date: str,
    lesson_date: str | None,
    description: str,
    status: TaskStatus,
    created_at: str,
    completed_at: str | None,
)

class TaskStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"
```

## PDF

### md_to_pdf

```python
from pathlib import Path
from bot.utils.__pdf import md_to_pdf

ok = md_to_pdf(Path("note.md"), Path("note.pdf"))
```

Конвертирует Markdown в PDF с формулами LaTeX (MathJax) и диаграммами Mermaid.

### upload_file и send_file

```python
from bot.utils.__pdf import upload_file, send_file

file_token = await upload_file(token, Path("note.pdf"), "file")
ok = await send_file(token, user_id, file_token, caption="Конспект")
```

Отправляет файл в MAX Bot API с автоматическим retry при `attachment.not.ready`.

## bot

### Регистрация хендлеров

```python
from bot.handlers import register_all

register_all(dp)
```

Регистрирует все команды и callback-и: `/start`, `/help`, `/help_notes`,
`/help_skeds`, `/help_tasks`, `/cancel`.

### Планировщик

```python
from bot.scheduler.reminders import run_reminders

asyncio.create_task(run_reminders(bot))
```

### Безопасность

```python
from bot.security import rate_limiter, extension_ok, file_size_ok, text_length_ok, total_size_ok

ok, reason = rate_limiter.check(user_id)
ok, reason = extension_ok("file.pdf")
ok, reason = file_size_ok(size_bytes)
ok, reason = total_size_ok(current_bytes, new_bytes)
ok, reason = text_length_ok(text)
```

### Хранилище

```python
from bot.session.storage import storage

storage.get_session(user_id)
storage.save_session(session)
storage.add_file(user_id, file)
storage.clear_files(user_id)

storage.get_user_settings(user_id)
storage.set_user_setting(user_id, key, value)

storage.add_reminder(user_id, kind, payload, fire_at)
storage.due_reminders(now_iso)
storage.mark_reminder_sent(reminder_id)
storage.has_any_reminder(user_id, kind, key)

storage.reset_user(user_id)
```

### Состояния сессии

```python
from bot.session.state import SessionState, Session, SessionFile

SessionState.IDLE
SessionState.AWAITING_SUBJECT
SessionState.AWAITING_TYPE
SessionState.COLLECTING_FILES
SessionState.PROCESSING
SessionState.AWAITING_DIGEST_TIME
SessionState.AWAITING_ALERT_MIN
SessionState.AWAITING_TASK_BEFORE_TIME
SessionState.AWAITING_TASK_TODAY_TIME
SessionState.AWAITING_SCHEDULE_FILE
SessionState.AWAITING_TASK_ADD
```

### Ошибки

```python
from bot.utils.__errors import report

await report(event, "action:name", err)
```

Пишет в лог и отправляет в чат сообщение с кнопкой «Скопировать текст ошибки».

### UI

```python
from bot.ui import chat_id, user_id
from bot.ui.__messages import safe_delete, delete_user_message, send_temp

chat = chat_id(event)
user = user_id(event)

await safe_delete(event, message_id)
await send_temp(event, "текст", seconds=5)
```
# bot — API

Справочник по внутренним интерфейсам чат-бота. Для обзора проекта — [../README.md](../README.md).

## Пакет `bot`

Точка входа — `bot/__main__.py`. Запускает `Bot`, `Dispatcher`, регистрирует хендлеры и фоновый планировщик.

```bash
python -m bot
```

Эквивалент: `based-bot` (объявлен в `pyproject.toml`).

## Конфигурация

### BotConfig

```python
from bot.config import config
```

Читает `bot/config/*.yaml` и `bot/config/.env`.

| Поле | Тип | По умолчанию | Описание |
|---|---|---|---|
| `token` | `str` | — | токен MAX (из `BOT_TOKEN`) |
| `cache_dir` | `Path` | `~/.cache/based-bot` | кеш бота |
| `db_path` | `Path` | `cache_dir / "sessions.db"` | SQLite сессий |
| `allowed_user_ids` | `list[str]` | `[]` | белый список |
| `ollama_host` | `str` | `http://localhost:11434` | адрес Ollama |
| `assets_base_url` | `str` | GitHub URL | архив промптов |
| `assets_version` | `str` | `v1.0.0` | версия архива |
| `max_file_size_mb` | `int` | `200` | лимит на файл |
| `max_total_size_mb` | `int` | `1000` | лимит на сессию |
| `max_files_per_session` | `int` | `30` | файлов на сессию |
| `max_text_length` | `int` | `10000` | символов в сообщении |
| `session_timeout_minutes` | `int` | `60` | таймаут сессии |
| `rate_per_minute` | `int` | `60` | лимит запросов в минуту |
| `rate_per_hour` | `int` | `300` | лимит запросов в час |
| `rate_ban_seconds` | `int` | `30` | длительность бана |
| `reminder_tick_seconds` | `int` | `10` | период планировщика |

## Хендлеры

### Регистрация

```python
from bot.handlers import register_all

register_all(dp)
```

Регистрирует команды и callback-и из `__router.py` и `__help.py`.

### Команды

| Команда | Хендлер | Описание |
|---|---|---|
| `/start` | `__router.start` | главное меню |
| `/help` | `__router.help_command` | общая справка |
| `/help_notes` | `__help.help_notes` | справка по конспектам |
| `/help_skeds` | `__help.help_skeds` | справка по расписанию |
| `/help_tasks` | `__help.help_tasks` | справка по ДЗ |
| `/cancel` | `__router.cancel_command` | отмена текущего сценария |

### Callback-и

Формат payload: `<namespace>:<action>[:<arg>]`.

| Namespace | Обработчик | Пример |
|---|---|---|
| `menu:` | `__menu.route` | `menu:notes`, `menu:schedule`, `menu:root` |
| `notes:` | `__conspect.route` | `notes:upload`, `notes:type:лекция`, `notes:generate` |
| `schedule:` | `__schedule.route` | `schedule:today`, `schedule:upload` |
| `tasks:` | `__tasks.route` | `tasks:list:pending`, `tasks:add`, `tasks:done:3` |
| `settings:` | `__settings.route` | `settings:notifications`, `settings:confirm:all` |
| `notif:` | `__settings.handle_notif` | `notif:toggle:digest_enabled`, `notif:set:digest_time` |
| `help:` | `__help.route` | `help:notes`, `help:skeds` |

### Порядок обработки сообщений

`__router.on_message` передаёт сообщение по цепочке:

1. `__conspect.handle_message` — состояния notes
2. `__settings.handle_notif_input` — ввод времени и минут
3. `__schedule.handle_message` — загрузка файла расписания
4. `__tasks.handle_message` — добавление ДЗ

Каждый хендлер возвращает `bool`: `True` — обработано, `False` — передать дальше.

## Публичные интерфейсы хендлеров

### __menu

```python
from bot.handlers import __menu

await __menu.show_root(event)      # главное меню
await __menu.show_help(event)      # справка
await __menu.route(event, "menu:notes")
```

### __help

```python
from bot.handlers import __help

await __help.route(event, "help:notes")
```

### __conspect

```python
from bot.handlers import __conspect

await __conspect.route(event, "notes:upload")
await __conspect.handle_message(event, text, attachments)  # -> bool
await __conspect.generate(event, user, chat)               # запуск пайплайна
await __conspect.cancel_session(event)                     # отмена
```

### __schedule

```python
from bot.handlers import __schedule

await __schedule.route(event, "schedule:today")
await __schedule.handle_message(event, attachments)  # -> bool
```

### __tasks

```python
from bot.handlers import __tasks

await __tasks.route(event, "tasks:list:pending")
await __tasks.handle_message(event, text)  # -> bool
```

### __settings

```python
from bot.handlers import __settings

await __settings.route(event, "settings:notifications")
await __settings.handle_notif(event, "notif:toggle:digest_enabled")  # -> bool
await __settings.handle_notif_input(event, "09:00")                  # -> bool
```

## Сессии

### Session

```python
from bot.session.state import Session, SessionFile, SessionState

Session(
    user_id: str,
    state: SessionState = SessionState.IDLE,
    subject: str | None = None,
    lesson_type: str | None = None,
    files: list[SessionFile] = [],
    status_message_id: str | None = None,
    started_at: str,
    updated_at: str,
)

SessionFile(
    file_id: str,
    file_type: str,   # audio | image | presentation | text | unknown
    local_path: str,
    size_bytes: int,
    added_at: str,
)
```

### SessionState

| Значение | Что означает |
|---|---|
| `IDLE` | ничего не происходит |
| `AWAITING_SUBJECT` | ждём название дисциплины |
| `AWAITING_TYPE` | ждём тип занятия |
| `COLLECTING_FILES` | собираем файлы |
| `PROCESSING` | идёт пайплайн |
| `AWAITING_DIGEST_TIME` | ждём время дайджеста |
| `AWAITING_ALERT_MIN` | ждём минуты для напоминания |
| `AWAITING_TASK_BEFORE_TIME` | ждём время напоминания за день |
| `AWAITING_TASK_TODAY_TIME` | ждём время напоминания в день |
| `AWAITING_SCHEDULE_FILE` | ждём файл расписания |
| `AWAITING_TASK_ADD` | ждём строку с задачей |

### Storage

```python
from bot.session.storage import storage
```

| Метод | Описание |
|---|---|
| `get_session(user_id) -> Session` | получить или создать сессию |
| `save_session(session) -> None` | сохранить |
| `list_active_sessions() -> list[dict]` | все не-IDLE сессии |
| `add_file(user_id, file) -> None` | добавить файл |
| `clear_files(user_id) -> None` | очистить файлы |
| `get_user_settings(user_id) -> dict` | настройки |
| `set_user_setting(user_id, key, value) -> None` | сохранить настройку |
| `list_user_settings() -> list[tuple]` | все настройки |
| `reset_user(user_id) -> None` | полный сброс |

### Файлы

```python
from bot.session.files import (
    save_bytes, attachment_url, attachment_name,
    detect_file_type, clear_session_files, clear_based_runs,
    total_size_bytes,
)

file = save_bytes(user_id, "lecture.mp3", data)
url = attachment_url(attachment)
name = attachment_name(attachment, fallback="file")
clear_session_files(user_id)
```

## Планировщик

### run_reminders

```python
from bot.scheduler.reminders import run_reminders

asyncio.create_task(run_reminders(bot))
```

Раз в `reminder_tick_seconds` секунд:

1. Создаёт напоминания по настройкам всех пользователей.
2. Отправляет due-напоминания.
3. Помечает просроченные как отправленные.
4. Удаляет занятия с `end_time <= now`.
5. Сбрасывает сессии старше `session_timeout_minutes`.

### Хранилище напоминаний

```python
storage.add_reminder(user_id, kind, payload, fire_at) -> int
storage.due_reminders(now_iso) -> list[dict]
storage.mark_reminder_sent(reminder_id) -> None
storage.purge_stale_reminders(now_iso, tolerance_seconds=300) -> None
storage.has_any_reminder(user_id, kind, key) -> bool
```

Виды напоминаний: `digest`, `lesson`, `task_before`, `task_today`.

## UI

### Хелперы

```python
from bot.ui import chat_id, user_id

chat = chat_id(event)
user = user_id(event)
```

### Клавиатуры

```python
from bot.ui.keyboards import (
    main_menu, notes_menu, schedule_menu, tasks_menu,
    settings_menu, notifications_menu, confirm_keyboard,
    lesson_type_keyboard, collecting_keyboard, error_keyboard,
    help_menu,
)

keyboard = main_menu()
```

### Сообщения

Все тексты — в `bot/ui/messages.py`. Форматирование через `str.format` или `string.Template`.

### Короткоживущие сообщения

```python
from bot.ui.__messages import safe_delete, delete_user_message, send_temp

await safe_delete(event, message_id)
await delete_user_message(event)
await send_temp(event, "Готово", seconds=5)
```

## Безопасность

### RateLimiter

```python
from bot.security import rate_limiter

ok, reason = rate_limiter.check(user_id)
```

Лимиты: `rate_per_minute`, `rate_per_hour`, бан на `rate_ban_seconds`.

### Проверки файлов

```python
from bot.security import (
    extension_ok, file_size_ok, total_size_ok, text_length_ok,
)

ok, reason = extension_ok("file.pdf")
ok, reason = file_size_ok(1024 * 1024)
ok, reason = total_size_ok(current_bytes, new_bytes)
ok, reason = text_length_ok("текст")
```

Белый список расширений и чёрный список — в `bot/config/security.yaml`.

## Ошибки

### report

```python
from bot.utils.__errors import report

await report(event, "action:name", err)
```

Пишет в лог `[bot] user=... action=... reason=...` и отправляет в чат сообщение с кнопкой «Скопировать текст ошибки».

## PDF

### md_to_pdf

```python
from bot.utils.__pdf import md_to_pdf

ok = md_to_pdf(Path("note.md"), Path("note.pdf"))
```

### upload_file и send_file

```python
from bot.utils.__pdf import upload_file, send_file

file_token = await upload_file(token, Path("note.pdf"), "file")
ok = await send_file(token, user_id, file_token, caption="Конспект")
```

`send_file` делает до 10 попыток при `attachment.not.ready`.

## Переменные окружения

Читаются из `bot/config/.env` или окружения процесса.

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | токен бота MAX |
| `BOT_CACHE_DIR` | каталог кеша |
| `BOT_ALLOWED_USER_IDS` | список ID через запятую |
| `OLLAMA_HOST` | адрес Ollama |
| `ASSETS_BASE_URL` | URL архива промптов |
| `ASSETS_VERSION` | версия архива |
"""
    Desc: inline keyboards for the MAX bot
    Creator: Kirosha
"""

from __future__ import annotations

from maxapi.types import ButtonsPayload, CallbackButton, ClipboardButton

from bot.session.state import LESSON_TYPES


def pack(rows: list[list]) -> ButtonsPayload:
    return ButtonsPayload(buttons=rows).pack()


def cb(text: str, payload: str) -> CallbackButton:
    return CallbackButton(text=text, payload=payload)


def clipboard(text: str, payload: str) -> ClipboardButton:
    return ClipboardButton(text=text, payload=payload)


def main_menu() -> ButtonsPayload:
    return pack(
        [
            [cb("Конспекты", "menu:notes")],
            [cb("Расписание", "menu:schedule")],
            [cb("Домашние задания", "menu:tasks")],
            [cb("Помощь", "menu:help"), cb("Настройки", "menu:settings")],
        ]
    )


def notes_menu(has_files: bool) -> ButtonsPayload:
    return pack(
        [
            [cb("Загрузить материал", "notes:upload")],
            [cb("Сгенерировать конспект", "notes:generate")],
            [cb("Назад", "menu:root")],
        ]
    )


def schedule_menu() -> ButtonsPayload:
    return pack(
        [
            [cb("Сегодня", "schedule:today"), cb("Завтра", "schedule:tomorrow")],
            [cb("На неделю", "schedule:week")],
            [cb("Загрузить файл", "schedule:upload")],
            [cb("Назад", "menu:root")],
        ]
    )


def tasks_menu() -> ButtonsPayload:
    return pack(
        [
            [cb("Активные", "tasks:list:pending"), cb("Выполненные", "tasks:list:done")],
            [cb("Отменённые", "tasks:list:cancelled"), cb("Все", "tasks:list:all")],
            [cb("Добавить", "tasks:add")],
            [cb("Назад", "menu:root")],
        ]
    )


def settings_menu() -> ButtonsPayload:
    return pack(
        [
            [cb("🔔 Уведомления", "settings:notifications")],
            [cb("🧹 Очистить кэш", "settings:cache")],
            [cb("📋 Сбросить задания", "settings:tasks")],
            [cb("📅 Сбросить расписание", "settings:schedule")],
            [cb("🗑 Сбросить всё", "settings:all")],
            [cb("Назад", "menu:root")],
        ]
    )


def confirm_keyboard(action: str) -> ButtonsPayload:
    return pack(
        [
            [cb("Да, удалить", f"settings:confirm:{action}")],
            [cb("Отмена", "menu:settings")],
        ]
    )


def lesson_type_keyboard() -> ButtonsPayload:
    return pack(
        [[cb(name.capitalize(), f"notes:type:{name}")] for name in LESSON_TYPES]
        + [[cb("Назад", "notes:back_to_subject")]]
    )


def collecting_keyboard() -> ButtonsPayload:
    return pack(
        [
            [cb("Сгенерировать конспект", "notes:generate")],
            [cb("Назад", "menu:root")],
        ]
    )


def error_keyboard(full_text: str) -> ButtonsPayload:
    return pack(
        [
            [clipboard("Скопировать текст ошибки", full_text[:900])],
            [cb("В меню", "menu:root")],
        ]
    )


def help_menu() -> ButtonsPayload:
    return pack(
        [
            [cb("📝 Конспекты", "help:notes")],
            [cb("📅 Расписание", "help:skeds")],
            [cb("📋 Домашние задания", "help:tasks")],
            [cb("Назад", "menu:root")],
        ]
    )


def notifications_menu(settings: dict) -> ButtonsPayload:
    digest = "вкл" if settings.get("digest_enabled") else "выкл"
    digest_time = settings.get("digest_time") or "не задано"
    alert = settings.get("lesson_alert_min")
    alert_text = f"за {alert} мин" if alert else "выкл"
    task_before = settings.get("task_day_before")
    task_before_at = settings.get("task_day_before_at") or "не задано"
    task_today = settings.get("task_due_today")
    task_today_at = settings.get("task_due_today_at") or "не задано"
    return pack(
        [
            [cb(f"🌅 Дайджест: {digest}", "notif:toggle:digest_enabled")],
            [cb(f"   время: {digest_time}", "notif:set:digest_time")],
            [cb(f"🔔 Пары: {alert_text}", "notif:toggle:lesson_alert_min")],
            [cb("   задать минуты", "notif:set:alert_min")],
            [cb(f"📋 Задачи за день: {'вкл' if task_before else 'выкл'}", "notif:toggle:task_day_before")],
            [cb(f"   время: {task_before_at}", "notif:set:task_before_at")],
            [cb(f"🔥 Задачи в день: {'вкл' if task_today else 'выкл'}", "notif:toggle:task_due_today")],
            [cb(f"   время: {task_today_at}", "notif:set:task_today_at")],
            [cb("Назад", "menu:settings")],
        ]
    )

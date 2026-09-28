"""
    Desc: single source of console output using rich
    Creator: Kirosha
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

console = Console(legacy_windows=False)
PREFIX = "\[based]"
_LOG_FILE: Path | None = None


def set_log_file(path: Path) -> None:
    global _LOG_FILE
    _LOG_FILE = path
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LOG_FILE.write_text("", encoding="utf-8")


def _write_file(tag: str, msg: str) -> None:
    if _LOG_FILE is None:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} [{tag}] {msg}\n")


def log_ok(msg: str) -> None:
    console.print(f"[bold green]{PREFIX}[/bold green] [green]OK[/green]   {escape(msg)}")
    _write_file("OK", msg)


def log_err(msg: str) -> None:
    console.print(f"[bold red]{PREFIX}[/bold red] [red]FAIL[/red] {escape(msg)}")
    _write_file("FAIL", msg)
    return None


def log_warn(msg: str) -> None:
    console.print(f"[bold yellow]{PREFIX}[/bold yellow] [yellow]WARN[/yellow] {escape(msg)}")
    _write_file("WARN", msg)


def log_step(msg: str) -> None:
    console.print(f"[bold blue]{PREFIX}[/bold blue] [blue]step[/blue] {escape(msg)}")
    _write_file("step", msg)


def log_info(msg: str) -> None:
    console.print(f"[bold white]{PREFIX}[/bold white] [white]info[/white] {escape(msg)}")
    _write_file("info", msg)


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def print_table(title: str, rows: dict, headers: tuple[str, str] = ("metric", "value")) -> None:
    table = Table(title=title)
    table.add_column(headers[0])
    table.add_column(headers[1])
    for metric, value in rows.items():
        table.add_row(escape(str(metric)), escape(str(value)))
    console.print(table)


def print_text(text: str) -> None:
    console.print(text, markup=False, highlight=False)


def print_issues(errors: list[str], warnings: list[str]) -> None:
    for error in errors:
        log_err(f"- {error}")
    for warning in warnings:
        log_warn(f"- {warning}")


def print_lessons(lessons: list[dict]) -> None:
    table = Table(title="lessons")
    for column in ("date", "start", "end", "subject", "teacher", "room", "type"):
        table.add_column(column)
    for lesson in lessons:
        table.add_row(
            escape(str(lesson.get("date") or "")),
            escape(str(lesson.get("start_time") or "")),
            escape(str(lesson.get("end_time") or "")),
            escape(str(lesson.get("subject") or "")),
            escape(str(lesson.get("teacher") or "")),
            escape(str(lesson.get("room") or "")),
            escape(str(lesson.get("lesson_type") or lesson.get("raw_type") or "")),
        )
    console.print(table)


def print_tasks(tasks: list[dict]) -> None:
    table = Table(title="tasks")
    for column in ("number", "subject", "due_date", "status", "description"):
        table.add_column(column)
    for task in tasks:
        description = str(task.get("description") or "")
        if len(description) > 40:
            description = description[:37] + "..."
        table.add_row(
            escape(str(task.get("task_number") or "")),
            escape(str(task.get("subject") or "")),
            escape(str(task.get("due_date") or "")),
            escape(str(task.get("status") or "")),
            escape(description),
        )
    console.print(table)

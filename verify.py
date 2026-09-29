"""
    Desc: verification for the hackathon scenario
    Creator: Kirosha

    Запуск:
        python verify.py            # быстрый режим (по умолчанию)
        python verify.py --quick    # явно быстрый
        python verify.py --full     # полный тест notes (долго, ~15 минут)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from based.utils.__console import log_err, log_ok, log_step, print_table

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
OUTPUT = SAMPLES / "output"


def check_imports() -> bool:
    try:
        import based
        from based import BasedAPI
        from based.modules.notes.api import NotesAPI
        from based.modules.skeds.api import SkedsAPI
        from based.modules.tasks.api import TasksAPI
        log_ok("imports ok")
        return True
    except Exception as err:
        log_err(f"imports failed: {err.__class__.__name__}: {err}")
        return False


def check_config() -> bool:
    try:
        from bot.config import config as bot_config
        from based.config import config as based_config
        rows = {
            "bot token set": bool(bot_config.token),
            "bot cache dir": str(bot_config.cache_dir),
            "based cache dir": str(based_config.cache_dir),
            "ollama": based_config.ollama_host,
        }
        print_table("config", rows)
        return True
    except Exception as err:
        log_err(f"config failed: {err.__class__.__name__}: {err}")
        return False


def check_prompts() -> bool:
    """Промпты должны лежать в репозитории, а не только в кеше ассетов."""
    try:
        from based.utils.__prompts import load_prompt
        rows = {}
        ok = True
        for module, name in (
            ("notes", "clean"),
            ("notes", "text"),
            ("notes", "user"),
            ("notes", "vision"),
            ("skeds", "schedule_parse"),
            ("skeds", "vision"),
        ):
            prompt = load_prompt(module, name)
            rows[f"{module}/{name}"] = "ok" if prompt else "missing"
            if prompt is None:
                ok = False
        print_table("prompts", rows)
        return ok
    except Exception as err:
        log_err(f"prompts failed: {err.__class__.__name__}: {err}")
        return False


def check_based_load(skip_setup: bool) -> bool:
    try:
        from based import BasedAPI
        api = BasedAPI()
        api.load(skip_setup=skip_setup)
        timings = api.timings()
        rows = {"total": f"{timings['total_seconds']:.3f}s"}
        for name, m in timings["modules"].items():
            rows[name] = f"{m.get('total_seconds', 0):.3f}s ({m.get('status', '?')})"
        print_table("based load", rows)
        return len(api.modules) >= 3
    except Exception as err:
        log_err(f"based load failed: {err.__class__.__name__}: {err}")
        return False


async def check_skeds() -> bool:
    csv = SAMPLES / "schedule_sample.csv"
    if not csv.exists():
        log_err(f"нет {csv}")
        return False
    try:
        from based.modules.skeds.api import SkedsAPI
        api = SkedsAPI()
        schedule = await api.parse(csv, group_name="__verify__")
        if schedule is None:
            log_err("skeds.parse вернул None (проверь ollama и модель)")
            return False
        print_table("skeds parse", {
            "group": schedule.group_name,
            "from": schedule.from_date,
            "to": schedule.to_date,
            "lessons": len(schedule.lessons),
        })
        return len(schedule.lessons) > 0
    except Exception as err:
        log_err(f"skeds failed: {err.__class__.__name__}: {err}")
        return False


def check_tasks() -> bool:
    try:
        from based.modules.tasks.api import TasksAPI
        api = TasksAPI()
        user = "__verify__"
        for old in api.list(user):
            api.hard_delete(user, old.task_number)
        task = api.add(user, "Тест", "2026-12-31", "проверка")
        ok = task.task_number == 1
        api.hard_delete(user, task.task_number)
        print_table("tasks", {"created": ok})
        return ok
    except Exception as err:
        log_err(f"tasks failed: {err.__class__.__name__}: {err}")
        return False


def check_pdf() -> bool:
    try:
        from bot.utils.__pdf import md_to_pdf
        src = SAMPLES / "note_sample.md"
        dst = OUTPUT / "note_sample.pdf"
        OUTPUT.mkdir(parents=True, exist_ok=True)
        ok = md_to_pdf(src, dst)
        if not ok:
            log_err("md_to_pdf вернул False")
            return False
        size = dst.stat().st_size
        print_table("pdf", {"path": str(dst), "size": f"{size} bytes"})
        return size > 0
    except Exception as err:
        log_err(f"pdf failed: {err.__class__.__name__}: {err}")
        return False


async def check_notes_fast() -> bool:
    """Быстрая проверка notes: конспект из текста, без аудио и whisper."""
    try:
        from based.modules.notes.api import NotesAPI, NoteRequest
    except Exception as err:
        log_err(f"notes import failed: {err.__class__.__name__}: {err}")
        return False

    text = (
        "Математический анализ изучает функции. Предел функции в точке "
        "определяется через эпсилон и дельту. Пример: предел x в квадрате "
        "при x стремящемся к двум равен четырём."
    )
    try:
        api = NotesAPI()
        request = NoteRequest(raw_text=text, subject_name="Быстрый тест")
        path = await api.create_note(request)
    except Exception as err:
        log_err(f"notes failed: {err.__class__.__name__}: {err}")
        return False

    if path is None:
        snapshot = api.health_check()
        errors = snapshot.get("errors") or ["неизвестная причина"]
        log_err(f"notes вернул None: {errors[0]}")
        return False

    size = path.stat().st_size
    print_table("notes fast", {"path": str(path), "size": f"{size} bytes"})
    return size > 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="verify")
    parser.add_argument(
        "--full",
        action="store_true",
        help="полный тест notes с аудио (~15 минут)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="быстрый режим, только текстовый конспект (по умолчанию)",
    )
    args = parser.parse_args()

    full = args.full and not args.quick
    mode = "full" if full else "quick"
    log_step(f"based + bot verification ({mode})")

    results = {
        "imports": check_imports(),
        "config": check_config(),
        "prompts": check_prompts(),
        "based load": check_based_load(skip_setup=not full),
        "skeds parse": asyncio.run(check_skeds()),
        "tasks": check_tasks(),
        "pdf": check_pdf(),
    }

    if full:
        results["notes full"] = False  # запускается отдельно через BasedAPI.load
    else:
        results["notes fast"] = asyncio.run(check_notes_fast())

    print_table("summary", {k: ("ok" if v else "fail") for k, v in results.items()})
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

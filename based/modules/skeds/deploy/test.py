"""
    Desc: smoke test for the skeds module across every discovered test set
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from pathlib import Path

from based.config import config
from based.modules.skeds.api import SkedsAPI
from based.utils.__assets import bundle, clear_runs, discover_tests
from based.utils.__console import log_err, log_ok, log_step, log_warn, print_issues, print_table
from based.utils.__json import write

MODULE = "skeds"


def _new_run_dir() -> Path:
    run_dir = config.cache_dir / MODULE / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


async def _run_test(name: str) -> str:
    assets = bundle(MODULE, name)
    files = sorted({path for paths in assets.values() for path in paths})
    if not files:
        log_err(f"{MODULE} {name}: no test assets found")
        return "fail: no test assets found"

    api = SkedsAPI()
    schedule = None
    source = None
    started = time.monotonic()
    for path in files:
        log_step(f"{MODULE} {name}: parsing {path.name}")
        schedule = await api.parse(path, group_name=name)
        if schedule is not None:
            source = path
            break
        log_warn(f"{MODULE} {name}: {path.name} did not parse, trying next")
    seconds = time.monotonic() - started

    snapshot = api.health_check()
    print_issues(snapshot["errors"], snapshot["warnings"])

    if schedule is None or source is None:
        reason = snapshot["errors"][0] if snapshot["errors"] else "no file parsed"
        log_err(f"{MODULE} {name}: no file parsed successfully")
        return f"fail: {reason}"

    run_dir = _new_run_dir()
    write(run_dir / "schedule.json", schedule.model_dump())
    lines = [
        f"{lesson.date} {lesson.start_time}-{lesson.end_time} {lesson.subject} | "
        f"{lesson.teacher or ''} | {lesson.room or ''}"
        for lesson in schedule.lessons
    ]
    (run_dir / "lessons.txt").write_text("\n".join(lines), encoding="utf-8")
    stats = {
        "source": str(source),
        "lessons_count": len(schedule.lessons),
        "from_date": schedule.from_date,
        "to_date": schedule.to_date,
        "seconds": round(seconds, 1),
    }
    write(run_dir / "stats.json", stats)
    print_table(f"{MODULE} {name}", {"run_dir": str(run_dir), **stats})
    log_ok(f"{MODULE} {name}: schedule parsed from {source.name}")
    return "ok"


async def _run() -> int:
    tests = discover_tests(MODULE)
    if not tests:
        log_err(f"{MODULE}: no tests found, run: based assets download")
        return 1
    clear_runs(MODULE)

    results: dict[str, str] = {}
    for name in tests:
        try:
            results[name] = await _run_test(name)
        except Exception as exc:
            log_err(f"{MODULE} {name}: {exc.__class__.__name__}: {exc}")
            results[name] = f"fail: {exc.__class__.__name__}: {exc}"

    print_table(f"{MODULE} test summary", results, headers=("test", "result"))
    return 0 if all(value == "ok" for value in results.values()) else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())

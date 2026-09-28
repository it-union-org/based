"""
    Desc: smoke test for the tasks module across every discovered scenario
    Creator: Kirosha
"""

from __future__ import annotations

import sys
import time
import uuid
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from based.config import config
from based.modules.tasks.api import TasksAPI
from based.modules.tasks.schemas import TaskStatus
from based.utils.__assets import clear_runs, discover_tests
from based.utils.__console import log_err, log_ok, log_step, print_issues, print_table
from based.utils.__json import write

MODULE = "tasks"


def _scenario_test_1(api: TasksAPI, user: str, actions: list[str]) -> str | None:
    first = api.add(user, "Математический анализ", "2026-10-01", "Глава 3, задачи 5-10")
    actions.append(f"add -> task {first.task_number}")
    if first.task_number != 1:
        return f"expected task_number 1, got {first.task_number}"

    second = api.add(user, "Физика", "2026-10-02", "Лабораторная работа 2")
    actions.append(f"add -> task {second.task_number}")
    if second.task_number != 2:
        return f"expected task_number 2, got {second.task_number}"

    pending = api.list(user, status=TaskStatus.PENDING.value)
    actions.append(f"list pending -> {len(pending)}")
    if len(pending) != 2:
        return f"expected 2 pending tasks, got {len(pending)}"

    api.mark_done(user, first.task_number)
    actions.append(f"mark_done {first.task_number}")
    pending = api.list(user, status=TaskStatus.PENDING.value)
    actions.append(f"list pending -> {len(pending)}")
    if len(pending) != 1:
        return f"expected 1 pending task after mark_done, got {len(pending)}"

    done = api.get(user, first.task_number)
    if done is None or done.status != TaskStatus.DONE:
        return "expected first task to have status done"
    return None


def _scenario_test_2(api: TasksAPI, user: str, actions: list[str]) -> str | None:
    task = api.add(user, "Физика", "2026-10-03", "Задача на отмену", lesson_date="2026-10-02")
    actions.append(f"add -> task {task.task_number}")
    api.mark_cancelled(user, task.task_number)
    actions.append(f"mark_cancelled {task.task_number}")
    cancelled = api.get(user, task.task_number)
    if cancelled is None or cancelled.status != TaskStatus.CANCELLED:
        return "expected task to have status cancelled"

    other = api.add(user, "Физика", "2026-10-04", "Отмена по занятию", lesson_date="2026-10-02")
    actions.append(f"add -> task {other.task_number}")
    count = api.cancel_for_lesson(user, "Физика", "2026-10-02")
    actions.append(f"cancel_for_lesson -> {count}")
    if count != 1:
        return f"expected 1 task cancelled for lesson, got {count}"

    subjects = api.subjects(user)
    actions.append(f"subjects -> {subjects}")
    if subjects:
        return f"expected no subjects for a user without group, got {subjects}"
    return None


SCENARIOS: dict[str, Callable[[TasksAPI, str, list[str]], str | None]] = {
    "test_1": _scenario_test_1,
    "test_2": _scenario_test_2,
}


def _new_run_dir() -> Path:
    run_dir = config.cache_dir / MODULE / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _run_test(name: str) -> str:
    scenario = SCENARIOS.get(name)
    if scenario is None:
        log_err(f"{MODULE} {name}: no scenario registered")
        return "fail: no scenario registered"

    api = TasksAPI()
    run_dir = _new_run_dir()
    user = f"test_user_{name}_{run_dir.name[:8]}"
    actions: list[str] = []
    log_step(f"{MODULE} {name}: running scenario as {user}")
    started = time.monotonic()
    reason = scenario(api, user, actions)
    seconds = time.monotonic() - started

    tasks = api.list(user)
    write(run_dir / "tasks.json", [task.model_dump(mode="json") for task in tasks])
    (run_dir / "actions.log").write_text("\n".join(actions), encoding="utf-8")
    counts = Counter(task.status.value for task in tasks)
    write(run_dir / "stats.json", {"counts": dict(counts), "seconds": round(seconds, 3)})

    snapshot = api.health_check()
    print_issues(snapshot["errors"], snapshot["warnings"])

    if reason is not None:
        log_err(f"{MODULE} {name}: {reason}")
        return f"fail: {reason}"

    print_table(f"{MODULE} {name}", {"run_dir": str(run_dir), "user": user, "tasks": len(tasks), **dict(counts)})
    log_ok(f"{MODULE} {name}: scenario passed")
    return "ok"


def main() -> int:
    tests = discover_tests(MODULE)
    if not tests:
        log_ok("nothing to run")
        return 0
    clear_runs(MODULE)

    results: dict[str, str] = {}
    for name in tests:
        try:
            results[name] = _run_test(name)
        except Exception as exc:
            log_err(f"{MODULE} {name}: {exc.__class__.__name__}: {exc}")
            results[name] = f"fail: {exc.__class__.__name__}: {exc}"

    print_table(f"{MODULE} test summary", results, headers=("test", "result"))
    return 0 if all(value == "ok" for value in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

"""
    Desc: tasks module commands
    Creator: Kirosha
"""

from __future__ import annotations

from based.utils.__console import log_err, print_table, print_tasks


def register(subparsers) -> None:
    tasks = subparsers.add_parser("tasks", help="tasks module commands")
    sub = tasks.add_subparsers(dest="tasks_command")

    add = sub.add_parser("add", help="add a task")
    add.add_argument("user")
    add.add_argument("subject")
    add.add_argument("due_date")
    add.add_argument("description")
    add.add_argument("--lesson-date", default=None)
    add.set_defaults(func=run_add)

    ls = sub.add_parser("list", help="list tasks")
    ls.add_argument("user")
    ls.add_argument("--status", default=None)
    ls.set_defaults(func=run_list)

    done = sub.add_parser("done", help="mark task done")
    done.add_argument("user")
    done.add_argument("number", type=int)
    done.set_defaults(func=run_done)

    cancel = sub.add_parser("cancel", help="mark task cancelled")
    cancel.add_argument("user")
    cancel.add_argument("number", type=int)
    cancel.set_defaults(func=run_cancel)

    subjects = sub.add_parser("subjects", help="list subjects available to user")
    subjects.add_argument("user")
    subjects.set_defaults(func=run_subjects)


def _api():
    try:
        from based.modules.tasks.api import TasksAPI
    except ImportError as exc:
        return log_err(f"tasks module not available: {exc}")
    return TasksAPI()


def run_add(args) -> int:
    api = _api()
    if api is None:
        return 1
    task = api.add(args.user, args.subject, args.due_date, args.description, args.lesson_date)
    print_table("task added", task.model_dump())
    return 0


def run_list(args) -> int:
    api = _api()
    if api is None:
        return 1
    tasks = api.list(args.user, status=args.status)
    print_tasks([task.model_dump() for task in tasks])
    return 0


def run_done(args) -> int:
    api = _api()
    if api is None:
        return 1
    api.mark_done(args.user, args.number)
    print_table("task done", {"user": args.user, "number": args.number})
    return 0


def run_cancel(args) -> int:
    api = _api()
    if api is None:
        return 1
    api.mark_cancelled(args.user, args.number)
    print_table("task cancelled", {"user": args.user, "number": args.number})
    return 0


def run_subjects(args) -> int:
    api = _api()
    if api is None:
        return 1
    subjects = api.subjects(args.user)
    if not subjects:
        print_table("subjects", {"result": "no subjects"})
        return 0
    for subject in subjects:
        print_table("subject", {"name": subject})
    return 0

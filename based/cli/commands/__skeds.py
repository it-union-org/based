"""
    Desc: skeds module commands for parsing and viewing schedules
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from based.utils.__console import log_err, print_lessons, print_table


def register(subparsers) -> None:
    skeds = subparsers.add_parser("skeds", help="skeds module commands")
    sub = skeds.add_subparsers(dest="skeds_command")

    parse = sub.add_parser("parse", help="parse a schedule file")
    parse.add_argument("file")
    parse.add_argument("--group", default=None)
    parse.set_defaults(func=run_parse)

    day = sub.add_parser("day", help="lessons for a group and date")
    day.add_argument("group")
    day.add_argument("date")
    day.set_defaults(func=run_day)

    rng = sub.add_parser("range", help="lessons for a group and date range")
    rng.add_argument("group")
    rng.add_argument("from_date")
    rng.add_argument("to_date")
    rng.set_defaults(func=run_range)


def _api():
    try:
        from based.modules.skeds.api import SkedsAPI
    except ImportError as exc:
        return log_err(f"skeds module not available: {exc}")
    return SkedsAPI()


def run_parse(args) -> int:
    api = _api()
    if api is None:
        return 1
    schedule = asyncio.run(api.parse(Path(args.file), group_name=args.group))
    if schedule is None:
        log_err("parse returned no schedule")
        return 1
    print_table(
        "schedule",
        {
            "group_name": schedule.group_name,
            "from_date": schedule.from_date,
            "to_date": schedule.to_date,
            "source": schedule.source,
            "lessons": len(schedule.lessons),
            "parsed_at": schedule.parsed_at,
        },
    )
    print_lessons([lesson.model_dump() for lesson in schedule.lessons])
    return 0


def run_day(args) -> int:
    api = _api()
    if api is None:
        return 1
    print_lessons(api.get_day(args.group, args.date))
    return 0


def run_range(args) -> int:
    api = _api()
    if api is None:
        return 1
    print_lessons(api.get_range(args.group, args.from_date, args.to_date))
    return 0

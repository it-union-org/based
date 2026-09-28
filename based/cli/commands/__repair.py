"""
    Desc: cli command that checks and repairs the based environment
    Creator: Kirosha
"""

from __future__ import annotations

import argparse

from based.repair import repair
from based.utils.__console import print_table


def run(args: argparse.Namespace) -> int:
    report = repair(fix=not args.check_only)
    rows = {
        check["name"]: ("ok" if check["ok"] else "fixed" if check["fixed"] else "fail")
        for check in report["checks"]
    }
    print_table("repair report", rows, headers=("check", "state"))
    return 0 if report["all_ok"] else 1


def register(subparsers) -> None:
    parser = subparsers.add_parser("repair", help="check and repair the based environment")
    parser.add_argument("--check-only", action="store_true", help="only check, do not fix")
    parser.set_defaults(func=run)

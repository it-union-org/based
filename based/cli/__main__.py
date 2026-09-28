"""
    Desc: entrypoint for the based cli, builds argparse and dispatches commands
    Creator: Kirosha
"""

from __future__ import annotations

import argparse
import sys

from based.cli.commands import (
    __assets,
    __info,
    __modules,
    __notes,
    __skeds,
    __tasks,
    __test,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="based", description="based cli")
    subparsers = parser.add_subparsers(dest="command")

    __info.register(subparsers)
    __modules.register(subparsers)
    __assets.register(subparsers)
    __skeds.register(subparsers)
    __tasks.register(subparsers)
    __notes.register(subparsers)
    __test.register(subparsers)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

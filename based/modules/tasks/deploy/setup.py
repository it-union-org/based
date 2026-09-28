"""
    Desc: idempotent setup checks for the tasks module
    Creator: Kirosha
"""

from __future__ import annotations

import sys

from based.utils.__console import log_err, log_ok

MIN_PYTHON = (3, 11)


def check_python() -> bool:
    if sys.version_info[:2] < MIN_PYTHON:
        log_err(
            f"python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, "
            f"found {sys.version_info[0]}.{sys.version_info[1]}"
        )
        return False
    log_ok("python version ok")
    return True


def main() -> int:
    return 0 if check_python() else 1


if __name__ == "__main__":
    sys.exit(main())

"""
    Desc: runs module deploy/test.py scripts
    Creator: Kirosha
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from based.utils.__console import log_err, print_table

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULES_DIR = PROJECT_ROOT / "based" / "modules"


def register(subparsers) -> None:
    test = subparsers.add_parser("test", help="run module test scripts")
    sub = test.add_subparsers(dest="test_command")

    one = sub.add_parser("module", help="run a single module test")
    one.add_argument("module")
    one.set_defaults(func=run_module)

    __all__ = sub.add_parser("all", help="run all module tests")
    __all__.set_defaults(func=run_all)


def _run_script(module: str) -> bool:
    script = MODULES_DIR / module / "deploy" / "test.py"
    if not script.exists():
        log_err(f"no test script for {module}")
        return False
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + existing if existing else "")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    return result.returncode == 0


def run_module(args) -> int:
    return 0 if _run_script(args.module) else 1


def run_all(_args) -> int:
    if not MODULES_DIR.exists():
        print_table("test all", {"modules": "none"})
        return 0
    results = {}
    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue
        results[module_dir.name] = "ok" if _run_script(module_dir.name) else "fail"
    print_table("test all", results)
    return 0 if all(v == "ok" for v in results.values()) else 1

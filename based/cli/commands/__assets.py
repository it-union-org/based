"""
    Desc: manages the assets archive cache
    Creator: Kirosha
"""

from __future__ import annotations

from pathlib import Path

from based.utils.__assets import discover_tests, ensure_assets, verify_test
from based.utils.__console import print_table

MODULES_DIR = Path(__file__).resolve().parents[2] / "modules"


def register(subparsers) -> None:
    assets = subparsers.add_parser("assets", help="asset operations")
    sub = assets.add_subparsers(dest="assets_command")

    dl = sub.add_parser("download", help="download and extract the assets archive")
    dl.add_argument("--force", action="store_true")
    dl.set_defaults(func=run_download)

    vf = sub.add_parser("verify", help="verify extracted assets")
    vf.set_defaults(func=run_verify)

    ls = sub.add_parser("list", help="list extracted tests per module")
    ls.set_defaults(func=run_list)


def run_download(args) -> int:
    ok = ensure_assets(force=args.force)
    print_table("assets download", {"ok": ok})
    return 0 if ok else 1


def run_verify(_args) -> int:
    if not MODULES_DIR.exists():
        print_table("assets verify", {"modules": "none"})
        return 0

    results = {}
    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue
        for test in discover_tests(module_dir.name):
            results[f"{module_dir.name}/{test}"] = verify_test(module_dir.name, test)

    if not results:
        print_table("assets verify", {"tests": "none"})
        return 0

    print_table("assets verify", results)
    return 0 if all(results.values()) else 1


def run_list(_args) -> int:
    if not MODULES_DIR.exists():
        print_table("assets", {"modules": "none"})
        return 0

    found = False
    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue
        tests = discover_tests(module_dir.name)
        if tests:
            found = True
            print_table(module_dir.name, {"tests": tests})

    if not found:
        print_table("assets", {"result": "no tests discovered"})
    return 0
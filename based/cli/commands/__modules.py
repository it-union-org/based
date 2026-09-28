"""
    Desc: lists loaded modules and their health
    Creator: Kirosha
"""

from __future__ import annotations

from based import BasedAPI
from based.utils.__console import print_table


def register(subparsers) -> None:
    modules = subparsers.add_parser("modules", help="list modules and status")
    modules.set_defaults(func=run_modules)

    health = subparsers.add_parser("health", help="health check of loaded modules")
    health.set_defaults(func=run_health)

    load = subparsers.add_parser("load", help="run BasedAPI.load()")
    load.add_argument("--skip-setup", action="store_true")
    load.set_defaults(func=run_load)


def run_modules(_args) -> int:
    api = BasedAPI()
    api.load(skip_setup=True)
    if not api.modules:
        print_table("modules", {"loaded": 0})
        return 0
    rows = {}
    for name, instance in api.modules.items():
        status = "?"
        if hasattr(instance, "health_check"):
            status = instance.health_check().get("status", "?")
        rows[name] = status
    print_table("modules", rows)
    return 0


def run_health(_args) -> int:
    api = BasedAPI()
    api.load(skip_setup=True)
    if not api.modules:
        print_table("health", {"modules": "none"})
        return 0
    for name, instance in api.modules.items():
        if not hasattr(instance, "health_check"):
            print_table(f"{name} health", {"status": "no health_check"})
            continue
        snapshot = instance.health_check()
        snapshot["errors"] = len(snapshot.get("errors", []))
        snapshot["warnings"] = len(snapshot.get("warnings", []))
        print_table(f"{name} health", snapshot)
    return 0


def run_load(args) -> int:
    api = BasedAPI()
    api.load(skip_setup=args.skip_setup)
    print_table(
        "loaded modules",
        {"count": len(api.modules), "names": ", ".join(api.modules)},
    )
    return 0

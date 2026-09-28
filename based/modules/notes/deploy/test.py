"""
    Desc: smoke test for the notes module across every discovered test set
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from based.modules.notes.api import NotesAPI
from based.modules.notes.schemas import NoteRequest
from based.utils.__assets import bundle, clear_runs, discover_tests
from based.utils.__console import log_err, log_ok, log_step, print_issues, print_table
from based.utils.__json import read_path

MODULE = "notes"
SUBJECT = "Тестовая лекция"


def _collect(assets: dict[str, list[Path]], keys: tuple[str, ...]) -> list[Path]:
    collected: list[Path] = []
    for key in keys:
        collected.extend(assets.get(key, []))
    return collected


async def _run_test(name: str) -> str:
    assets = bundle(MODULE, name)
    audio_paths = _collect(assets, ("audios", "audio"))
    image_paths = _collect(assets, ("images", "image"))
    presentations = _collect(assets, ("presentation", "presentations"))
    if not audio_paths and not image_paths and not presentations:
        log_err(f"{MODULE} {name}: no test assets found")
        return "fail: no test assets found"

    api = NotesAPI()
    request = NoteRequest(
        audio_paths=audio_paths,
        #image_paths=image_paths,
        #presentation_path=presentations[0] if presentations else None,
        subject_name=SUBJECT,
    )
    log_step(f"{MODULE} {name}: create_note")
    started = time.monotonic()
    note_path = await api.create_note(request)
    seconds = time.monotonic() - started

    snapshot = api.health_check()
    print_issues(snapshot["errors"], snapshot["warnings"])

    if note_path is None:
        reason = snapshot["errors"][0] if snapshot["errors"] else "create_note returned no note"
        log_err(f"{MODULE} {name}: create_note returned no note")
        return f"fail: {reason}"

    stats = read_path(note_path.parent / "stats.json")
    print_table(f"{MODULE} {name}", {"note_path": str(note_path), "seconds": f"{seconds:.1f}", **stats})
    log_ok(f"{MODULE} {name}: note created")
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

"""
    Desc: notes module commands
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from based.utils.__console import log_err, print_table
from based.utils.__json import read_path


def register(subparsers) -> None:
    notes = subparsers.add_parser("notes", help="notes module commands")
    sub = notes.add_subparsers(dest="notes_command")

    create = sub.add_parser("create", help="create a note from files and text")
    create.add_argument("subject")
    create.add_argument("--audio", action="append", default=[])
    create.add_argument("--image", action="append", default=[])
    create.add_argument("--presentation", default=None)
    create.add_argument("--text", default=None)
    create.set_defaults(func=run_create)

    from_text = sub.add_parser("from-text", help="create a note from a text file")
    from_text.add_argument("file")
    from_text.add_argument("subject")
    from_text.set_defaults(func=run_from_text)


def _api():
    try:
        from based.modules.notes.api import NotesAPI, NoteRequest
    except ImportError as exc:
        return None, None, log_err(f"notes module not available: {exc}")
    return NotesAPI(), NoteRequest, None


def run_create(args) -> int:
    api, NoteRequest, err = _api()
    if api is None:
        return 1
    request = NoteRequest(
        audio_paths=[Path(p) for p in args.audio],
        image_paths=[Path(p) for p in args.image],
        presentation_path=Path(args.presentation) if args.presentation else None,
        raw_text=args.text,
        subject_name=args.subject,
    )
    note_path = asyncio.run(api.create_note(request))
    if note_path is None:
        log_err("create_note returned no note")
        return 1
    stats = read_path(note_path.parent / "stats.json")
    print_table("note created", {"note_path": str(note_path), **stats})
    return 0


def run_from_text(args) -> int:
    api, _NoteRequest, err = _api()
    if api is None:
        return 1
    text = Path(args.file).read_text(encoding="utf-8")
    note_path = asyncio.run(api.create_note_from_text(text, args.subject))
    if note_path is None:
        log_err("create_note_from_text returned no note")
        return 1
    print_table("note created", {"note_path": str(note_path)})
    return 0

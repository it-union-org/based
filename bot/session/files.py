"""
    Desc: downloads and stores user files in the bot cache
    Creator: Kirosha
"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from bot.config import config
from bot.session.state import SessionFile

AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".flac", ".aac"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic"}
PRESENTATION_EXT = {".pdf", ".pptx", ".ppt"}
TEXT_EXT = {".txt", ".md"}


def payload_get(payload, key: str, default=None):
    if payload is None:
        return default
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def attachment_url(attachment) -> str | None:
    payload = getattr(attachment, "payload", None)
    url = payload_get(payload, "url")
    if url:
        return str(url)
    return None


def attachment_name(attachment, fallback: str = "file") -> str:
    payload = getattr(attachment, "payload", None)
    for key in ("filename", "file_name", "name"):
        value = payload_get(payload, key)
        if value:
            return str(value)
    value = getattr(attachment, "filename", None) or getattr(attachment, "file_name", None)
    if value:
        return str(value)
    return fallback


def session_dir(user_id: str) -> Path:
    path = config.cache_dir / "sessions" / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_session_files(user_id: str) -> None:
    shutil.rmtree(config.cache_dir / "sessions" / user_id, ignore_errors=True)


def clear_based_runs() -> None:
    from based.config import config as based_config

    for name in ("notes", "skeds", "tasks"):
        shutil.rmtree(based_config.cache_dir / name, ignore_errors=True)


def detect_file_type(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in AUDIO_EXT:
        return "audio"
    if suffix in IMAGE_EXT:
        return "image"
    if suffix in PRESENTATION_EXT:
        return "presentation"
    if suffix in TEXT_EXT:
        return "text"
    return "unknown"


def guess_ext_from_bytes(data: bytes) -> str:
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    if data[:8].startswith(b"\x00\x00\x00") and b"ftyp" in data[:16]:
        return ".m4a"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return ".wav"
    if data[:4] == b"OggS":
        return ".ogg"
    if data[:4] == b"fLaC":
        return ".flac"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:4] == b"%PDF":
        return ".pdf"
    if data[:4] == b"PK\x03\x04":
        return ".zip"
    return ""


def classify_by_bytes(data: bytes) -> str:
    ext = guess_ext_from_bytes(data)
    if ext in {".mp3", ".m4a", ".wav", ".ogg", ".flac"}:
        return "audio"
    if ext in {".jpg", ".png", ".webp"}:
        return "image"
    if ext == ".pdf":
        return "presentation"
    return "unknown"


def save_bytes(user_id: str, original_name: str, data: bytes) -> SessionFile:
    file_type = detect_file_type(original_name)
    if file_type == "unknown":
        file_type = classify_by_bytes(data)

    original_ext = Path(original_name).suffix.lower()
    if not original_ext:
        guessed = guess_ext_from_bytes(data)
        if guessed:
            original_name = f"{original_name}{guessed}"

    folder = session_dir(user_id) / (file_type if file_type != "unknown" else "files")
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(original_name).name}"
    target = folder / safe_name
    target.write_bytes(data)
    return SessionFile(
        file_id=uuid.uuid4().hex,
        file_type=file_type,
        local_path=str(target),
        size_bytes=len(data),
        added_at=datetime.now().isoformat(),
    )


def total_size_bytes(user_id: str) -> int:
    folder = config.cache_dir / "sessions" / user_id
    if not folder.exists():
        return 0
    total = 0
    for path in folder.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total

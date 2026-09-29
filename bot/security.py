"""
    Desc: rate limiting and file safety checks for the bot
    Creator: Kirosha
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from pathlib import Path

from bot.config import config
from bot.ui.messages import (
    EXTENSION_BLOCKED,
    EXTENSION_UNKNOWN,
    FILE_TOO_LARGE,
    RATE_LIMIT_BAN,
    RATE_LIMIT_HOUR,
    TOTAL_TOO_LARGE,
)
from based.utils.__console import log_warn

ALLOWED_EXTENSIONS = {
    ".mp3", ".m4a", ".wav", ".ogg", ".opus", ".flac", ".aac",
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic",
    ".pdf", ".pptx", ".ppt", ".xlsx", ".xls", ".docx", ".doc",
    ".csv", ".tsv", ".txt", ".md", ".rtf", ".ics", ".json",
}

BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".py", ".dll", ".so", ".dylib",
    ".bin", ".com", ".msi", ".scr", ".vbs", ".jar", ".app",
}


class RateLimiter:
    def __init__(self) -> None:
        self.__events: dict[str, deque] = defaultdict(deque)
        self.__bans: dict[str, float] = {}

    def check(self, user_id: str) -> tuple[bool, str]:
        now = time.monotonic()
        ban_until = self.__bans.get(user_id)
        if ban_until and ban_until > now:
            left = int(ban_until - now)
            return False, RATE_LIMIT_BAN.format(seconds=left)

        events = self.__events[user_id]
        while events and events[0] < now - 3600:
            events.popleft()

        hour_count = sum(1 for t in events if t > now - 3600)
        if hour_count >= config.rate_per_hour:
            self.__bans[user_id] = now + config.rate_ban_seconds
            log_warn(f"bot rate limit user={user_id} action=hour count={hour_count} limit={config.rate_per_hour}")
            return False, RATE_LIMIT_HOUR.format(seconds=config.rate_ban_seconds)

        minute_count = sum(1 for t in events if t > now - 60)
        if minute_count >= config.rate_per_minute:
            self.__bans[user_id] = now + config.rate_ban_seconds
            log_warn(f"bot rate limit user={user_id} action=minute count={minute_count} limit={config.rate_per_minute}")
            return False, RATE_LIMIT_BAN.format(seconds=config.rate_ban_seconds)

        events.append(now)
        return True, ""


rate_limiter = RateLimiter()


def file_size_ok(size_bytes: int) -> tuple[bool, str]:
    limit = config.max_file_size_mb * 1024 * 1024
    if size_bytes > limit:
        mb = size_bytes / (1024 * 1024)
        return False, FILE_TOO_LARGE.format(size=mb, limit=config.max_file_size_mb)
    return True, ""


def total_size_ok(current_bytes: int, new_bytes: int) -> tuple[bool, str]:
    limit = config.max_total_size_mb * 1024 * 1024
    if current_bytes + new_bytes > limit:
        mb = (current_bytes + new_bytes) / (1024 * 1024)
        return False, TOTAL_TOO_LARGE.format(size=mb, limit=config.max_total_size_mb)
    return True, ""


def extension_ok(name: str) -> tuple[bool, str]:
    suffix = Path(name).suffix.lower()
    if suffix in BLOCKED_EXTENSIONS:
        return False, EXTENSION_BLOCKED.format(ext=suffix)
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        return False, EXTENSION_UNKNOWN.format(ext=suffix)
    return True, ""


def text_length_ok(text: str) -> tuple[bool, str]:
    if len(text) > config.max_text_length:
        return False, f"Сообщение слишком длинное ({len(text)} символов). Лимит: {config.max_text_length}."
    return True, ""

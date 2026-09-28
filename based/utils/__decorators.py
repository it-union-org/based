"""
    Desc: reusable decorators for safe calls, retries and timing
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Callable

from based.utils.__console import log_err, log_warn


def safe_call(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            log_err(f"{func.__name__} failed: {err.__class__.__name__}: {err}")
            return None
    return wrapper


def safe_async(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            log_err(f"{func.__name__} failed: {err.__class__.__name__}: {err}")
            return None
    return wrapper


def retry_async(attempts: int, sleep: float, label: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last = "no attempts made"
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as err:
                    last = f"{err.__class__.__name__}: {err}"
                    log_warn(f"{label} attempt {attempt}/{attempts}: {last}")
                    await asyncio.sleep(sleep)
            log_err(f"{label} failed after {attempts} attempts: {last}")
            return None
        return wrapper
    return decorator


def measure(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        started = time.monotonic()
        result = func(*args, **kwargs)
        log_warn(f"{func.__name__} took {time.monotonic() - started:.2f}s")
        return result
    return wrapper

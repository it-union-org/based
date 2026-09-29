"""
    Desc: entry point of the MAX bot
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
import logging
import sys

from maxapi import Bot, Dispatcher

from bot.config import config
from bot.handlers import register_all
from bot.scheduler.reminders import run_reminders

from based.utils.__console import log_err


logging.basicConfig(level=logging.WARNING)


async def run() -> int:
    if not config.token:
        log_err("BOT_TOKEN is not set")
        return 1
    if not config.cache_dir.exists():
        config.cache_dir.mkdir(parents=True, exist_ok=True)

    bot = Bot(config.token)
    dp = Dispatcher()
    register_all(dp)

    scheduler = asyncio.create_task(run_reminders(bot))
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.cancel()
        try:
            await scheduler
        except (asyncio.CancelledError, Exception):
            pass
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())

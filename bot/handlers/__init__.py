"""
    Desc: handlers registry
    Creator: Kirosha
"""

from __future__ import annotations

from bot.handlers import __help, __router


def register_all(dp) -> None:
    __help.register(dp)
    __router.register(dp)

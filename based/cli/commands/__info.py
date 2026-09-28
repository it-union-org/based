"""
    Desc: prints package info and current configuration
    Creator: Kirosha
"""

from __future__ import annotations

from based import __version__
from based.config import config
from based.utils.__console import print_table


def register(subparsers) -> None:
    parser = subparsers.add_parser("info", help="print package and config info")
    parser.set_defaults(func=run)


def run(_args) -> int:
    print_table(
        "based info",
        {
            "version": __version__,
            "cache_dir": str(config.cache_dir),
            "db_path": str(config.db_path),
            "ollama_host": config.ollama_host,
            "assets_base_url": config.assets_base_url,
            "assets_version": config.assets_version,
            "text_model": config.text_model,
            "vision_model": config.vision_model,
            "whisper_model": config.whisper_model,
            "text_num_ctx": config.text_num_ctx,
            "text_num_predict": config.text_num_predict,
            "vision_num_ctx": config.vision_num_ctx,
            "vision_num_predict": config.vision_num_predict,
        },
    )
    return 0

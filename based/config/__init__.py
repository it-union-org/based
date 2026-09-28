"""
    Desc: package-level configuration loaded from yaml and env
    Creator: Kirosha
"""

from __future__ import annotations

import os
from pathlib import Path

from based.utils.__env import read_env
from based.utils.__json import read

DEFAULT_CACHE_DIR = "~/.cache/based"
DEFAULT_ASSETS_BASE_URL = "https://github.com/it-union-org/assets/releases/download"
DEFAULT_ASSETS_VERSION = "v1.0.0"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"


class Config:
    def __init__(self) -> None:
        env = read_env()
        paths = read("paths")
        models = read("models")
        limits = read("limits")
        db = read("db")

        cache_dir = Path(os.path.expanduser(paths.get("cache_dir", DEFAULT_CACHE_DIR)))

        self.cache_dir: Path = cache_dir
        self.db_path: Path = Path(os.path.expanduser(db.get("path", str(cache_dir / "based.db"))))

        self.assets_base_url: str = env.get("ASSETS_BASE_URL", DEFAULT_ASSETS_BASE_URL)
        self.assets_version: str = env.get("ASSETS_VERSION", DEFAULT_ASSETS_VERSION)
        self.ollama_host: str = env.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)

        self.text_model: str = models.get("text_model", "")
        self.vision_model: str = models.get("vision_model", "")
        self.whisper_model: str = models.get("whisper_model", "")
        self.whisper_device: str = models.get("whisper_device", "auto")

        self.llm_max_retries: int = int(limits.get("llm_max_retries", 3))
        self.llm_retry_sleep: float = float(limits.get("llm_retry_sleep", 1.5))
        self.llm_request_timeout: float = float(limits.get("llm_request_timeout", 600.0))
        self.llm_error_body_limit: int = int(limits.get("llm_error_body_limit", 500))

        self.text_num_ctx: int = int(limits.get("text_num_ctx", 16384))
        self.text_num_predict: int = int(limits.get("text_num_predict", 4096))
        self.vision_num_ctx: int = int(limits.get("vision_num_ctx", 8192))
        self.vision_num_predict: int = int(limits.get("vision_num_predict", 2048))

        self.vision_max_image_side: int = int(limits.get("vision_max_image_side", 1024))
        self.vision_jpeg_quality: int = int(limits.get("vision_jpeg_quality", 85))

        self.whisper_language: str = str(limits.get("whisper_language", "ru"))
        self.whisper_beam_size: int = int(limits.get("whisper_beam_size", 1))
        self.whisper_vad_filter: bool = bool(limits.get("whisper_vad_filter", True))
        self.whisper_progress_every: int = int(limits.get("whisper_progress_every", 50))

        self.clean_chunk_size: int = int(limits.get("clean_chunk_size", 7000))
        self.format_chunk_size: int = int(limits.get("format_chunk_size", 10000))
        self.min_text_chars_per_page: int = int(limits.get("min_text_chars_per_page", 200))

        self.max_input_chars: int = int(limits.get("max_input_chars", 120000))
        self.presentation_render_scale: float = float(limits.get("presentation_render_scale", 2.0))

        self.health_max_errors: int = int(limits.get("health_max_errors", 64))
        self.health_max_warnings: int = int(limits.get("health_max_warnings", 64))

        self.assets_download_timeout: float = float(limits.get("assets_download_timeout", 120.0))
        self.assets_error_body_limit: int = int(limits.get("assets_error_body_limit", 800))

        self.min_python_version: tuple = tuple(limits.get("min_python_version", [3, 11]))


config = Config()

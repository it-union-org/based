"""
    Desc: idempotent setup checks for the notes module
    Creator: Kirosha
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from based.config import config
from based.utils.__console import log_err, log_ok, log_warn
from based.utils.__llm import get_tags

MIN_PYTHON = (3, 11)


def check_python() -> bool:
    if sys.version_info[:2] < MIN_PYTHON:
        log_err(
            f"python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, "
            f"found {sys.version_info[0]}.{sys.version_info[1]}"
        )
        return False
    log_ok("python version ok")
    return True


def check_ffmpeg() -> bool:
    if shutil.which("ffmpeg") is None:
        log_err("ffmpeg not found in PATH")
        return False
    log_ok("ffmpeg found in PATH")
    return True


def check_ollama_reachable() -> bool:
    tags = get_tags()
    if tags is None:
        log_err(f"ollama not reachable at {config.ollama_host}")
        return False
    log_ok(f"ollama reachable at {config.ollama_host}")
    return True


def check_whisper_model() -> bool:
    log_warn(f"whisper model {config.whisper_model} downloads on first use via faster-whisper")
    return True


def check_model(name: str, tags: list[str], force: bool) -> bool:
    if not force and any(name in tag for tag in tags):
        log_ok(f"model present: {name}")
        return True
    log_warn(f"pulling model: {name}")
    result = subprocess.run(["ollama", "pull", name])
    if result.returncode != 0:
        log_err(f"failed to pull model: {name}")
        return False
    log_ok(f"model pulled: {name}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not check_python():
        return 1
    if not check_ffmpeg():
        return 1
    if not check_ollama_reachable():
        return 1

    check_whisper_model()

    tags = get_tags() or []
    ok = True
    for model in (config.text_model, config.vision_model):
        if not check_model(model, tags, args.force):
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

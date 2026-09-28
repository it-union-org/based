"""
    Desc: llm-backed agents wrapping transcription, vision and summarization
    Creator: Kirosha
"""

from __future__ import annotations

from pathlib import Path

from based.utils.__console import log_err
from based.utils.__llm import ask_text, ask_vision, last_error, transcribe
from based.utils.__prompts import load_prompt


class Transcriber:
    def __init__(self) -> None:
        self.last_error: str | None = None

    async def transcribe(self, path: Path) -> str | None:
        self.last_error = None
        result = await transcribe(path)
        if result is None:
            self.last_error = last_error() or "transcription failed without details"
        return result


class Vision:
    def __init__(self) -> None:
        self.__prompt: str | None = None
        self.last_error: str | None = None

    def __get_prompt(self) -> str | None:
        if self.__prompt is None:
            self.__prompt = load_prompt("notes", "vision")
        return self.__prompt

    async def describe(self, image_path: Path) -> str | None:
        self.last_error = None
        prompt = self.__get_prompt()
        if prompt is None:
            self.last_error = "vision prompt not found"
            return log_err("vision prompt not found")
        result = await ask_vision(prompt, image_path)
        if result is None:
            self.last_error = last_error() or "vision request failed without details"
        return result


class Summarizer:
    def __init__(self) -> None:
        self.__prompt: str | None = None
        self.last_error: str | None = None

    def __get_prompt(self) -> str | None:
        if self.__prompt is None:
            self.__prompt = load_prompt("notes", "text")
        return self.__prompt

    async def summarize(self, user_prompt: str) -> str | None:
        self.last_error = None
        prompt = self.__get_prompt()
        if prompt is None:
            self.last_error = "text prompt not found"
            return log_err("text prompt not found")
        result = await ask_text(prompt, user_prompt)
        if result is None:
            self.last_error = last_error() or "summarization failed without details"
        return result

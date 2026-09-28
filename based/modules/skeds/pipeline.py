"""
    Desc: extraction and llm pipeline that turns source files into schedules
    Creator: Kirosha
"""

from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Awaitable, Callable

from based.config import config
from based.modules.skeds.extractors import extract
from based.modules.skeds.schemas import Schedule, ScheduleRequest
from based.modules.skeds.settings import SkedsSettings
from based.utils.__console import log_err, log_warn
from based.utils.__db import BasedDB
from based.utils.__health import HealthState, health_check
from based.utils.__llm import ask_text, ask_vision, last_error
from based.utils.__prompts import load_prompt

ProgressCallback = Callable[[str], Awaitable[None]]


class Pipeline:
    def __init__(self, settings: SkedsSettings, db: BasedDB) -> None:
        self.settings = settings
        self.db = db
        self.health = HealthState()

    @contextmanager
    def __cleanup(self, dirs: list[Path]):
        try:
            yield
        finally:
            for temp_dir in dirs:
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def __progress(self, cb: ProgressCallback | None, msg: str) -> None:
        if cb is not None:
            try:
                await cb(msg)
            except Exception:
                pass

    @health_check("parse")
    async def parse(
        self,
        request: ScheduleRequest,
        progress_cb: ProgressCallback | None = None,
    ) -> Schedule | None:
        await self.__progress(progress_cb, "Читаю файл расписания...")
        extracted = extract(request.source)
        with self.__cleanup(extracted.temp_dirs):
            if not extracted.text and not extracted.tables and not extracted.images:
                self.health.report_error(f"nothing extracted from {request.source.name}")
                return log_err(f"skeds: nothing extracted from {request.source.name}")

            await self.__progress(progress_cb, "Извлекаю текст...")
            descriptions: list[str] = []
            if extracted.images:
                vision_prompt = load_prompt("skeds", "vision")
                if vision_prompt is None:
                    self.health.report_warning("vision prompt not found")
                else:
                    for image in extracted.images:
                        description = await ask_vision(vision_prompt, image)
                        if description is None:
                            self.health.report_warning(f"vision failed for {image.name}: {last_error()}")
                            continue
                        descriptions.append(description)

            tables_text = "\n\n".join(
                "\n".join(" | ".join(cell or "" for cell in row) for row in table)
                for table in extracted.tables
            )
            combined = "\n\n".join(
                part for part in (extracted.text, tables_text, "\n\n".join(descriptions)) if part
            )
            if len(combined) > config.max_input_chars:
                log_warn(f"skeds: input truncated from {len(combined)} to {config.max_input_chars} chars")
                combined = combined[:config.max_input_chars]

            schedule_prompt = load_prompt("skeds", "schedule_parse")
            if schedule_prompt is None:
                self.health.report_error("schedule_parse prompt missing")
                return log_err("skeds: schedule_parse prompt missing")

            await self.__progress(progress_cb, "Разбираю расписание...")
            for attempt in range(1, self.settings.max_retries + 1):
                raw = await ask_text(schedule_prompt, combined)
                if raw is None:
                    self.health.report_warning(f"attempt {attempt}: {last_error()}")
                    continue
                schedule = self.__parse_response(raw, request)
                if schedule is not None:
                    await self.__progress(progress_cb, "Сохраняю в базу...")
                    self.__save(schedule, request.source)
                    return schedule
                log_warn(f"skeds: attempt {attempt}: invalid json or schema")

            self.health.report_error("failed to parse schedule")
            return log_err("skeds: failed to parse schedule")

    def __parse_response(self, raw: str, request: ScheduleRequest) -> Schedule | None:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        try:
            payload = json.loads(text)
            if request.group_name:
                payload["group_name"] = request.group_name
            return Schedule.model_validate(payload)
        except Exception:
            return None

    def __save(self, schedule: Schedule, source: Path) -> None:
        self.db.upsert_group(schedule.group_name, tenant=None, source=str(source))
        self.db.upsert_schedule(
            schedule.group_name,
            schedule.from_date,
            schedule.to_date,
            str(source),
            [lesson.model_dump() for lesson in schedule.lessons],
        )

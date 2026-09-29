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
from based.utils.__console import log_err, log_ok, log_step, log_warn
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
                log_warn(f"skeds: attempt {attempt}/{self.settings.max_retries}: invalid json or schema")

            self.health.report_error("failed to parse schedule")
            return log_err("skeds: failed to parse schedule")

    def __parse_response(self, raw: str, request: ScheduleRequest) -> Schedule | None:
        from based.utils.__console import log_err, log_step, log_warn

        text = raw.strip()
        log_step(f"skeds: response length={len(text)} chars, first 200: {text[:200]!r}")

        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
            log_step("skeds: stripped code fences")

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as err:
            log_err(f"skeds: json decode failed: {err}")
            log_err(f"skeds: raw text around error: {text[max(0, err.pos-80):err.pos+80]!r}")
            return None

        log_step(f"skeds: json parsed, top keys={list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}")

        if request.group_name:
            payload["group_name"] = request.group_name

        try:
            schedule = Schedule.model_validate(payload)
        except Exception as err:
            log_err(f"skeds: schema validation failed: {err.__class__.__name__}: {err}")
            return None

        log_ok(f"skeds: schedule ok, lessons={len(schedule.lessons)}")
        return schedule

    def __save(self, schedule: Schedule, source: Path) -> None:
        from based.utils.__console import log_step, log_err

        log_step(f"skeds __save: group={schedule.group_name!r} "
                 f"from={schedule.from_date!r} to={schedule.to_date!r} "
                 f"lessons={len(schedule.lessons)}")

        self.db.upsert_group(schedule.group_name, tenant=None, source=str(source))

        dumps = []
        for i, lesson in enumerate(schedule.lessons):
            try:
                d = lesson.model_dump()
                dumps.append(d)
            except Exception as err:
                log_err(f"lesson {i} model_dump failed: {err.__class__.__name__}: {err}")
                raise

        log_step(f"skeds __save: dumps={len(dumps)} keys={list(dumps[0].keys()) if dumps else 'empty'}")

        try:
            sid = self.db.upsert_schedule(
                schedule.group_name,
                schedule.from_date,
                schedule.to_date,
                str(source),
                dumps,
            )
        except Exception as err:
            log_err(f"upsert_schedule failed: {err.__class__.__name__}: {err}")
            raise

        log_step(f"skeds __save: schedule_id={sid}")

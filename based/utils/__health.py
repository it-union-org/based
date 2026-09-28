"""
    Desc: health state tracking with metrics, timings and stage history
    Creator: Kirosha
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from based.config import config


class HealthStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class StageMetrics:
    name: str
    started: float
    finished: float | None = None
    result: str = "running"
    error: str | None = None

    @property
    def duration(self) -> float:
        end = self.finished if self.finished is not None else time.monotonic()
        return end - self.started


@dataclass
class HealthState:
    status: HealthStatus = HealthStatus.IDLE
    current: str | None = None
    last: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stages: list[StageMetrics] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def report_error(self, msg: str) -> None:
        self.errors.append(msg)
        if len(self.errors) > config.health_max_errors:
            self.errors.pop(0)

    def report_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        if len(self.warnings) > config.health_max_warnings:
            self.warnings.pop(0)

    def increment(self, key: str, value: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + value

    def snapshot(self) -> dict:
        return {
            "status": self.status.value,
            "current": self.current,
            "last": self.last,
            "started_at": self.started_at,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "counters": dict(self.counters),
            "stages": [
                {
                    "name": stage.name,
                    "result": stage.result,
                    "duration": round(stage.duration, 3),
                    "error": stage.error,
                }
                for stage in self.stages
            ],
        }


def health_check(label: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        async def wrapper(self, *args, **kwargs):
            state: HealthState = self.health
            stage = StageMetrics(name=label, started=time.monotonic())
            state.stages.append(stage)
            state.status = HealthStatus.RUNNING
            state.current = label
            try:
                result = await func(self, *args, **kwargs)
            except Exception as err:
                stage.finished = time.monotonic()
                stage.result = "fail"
                stage.error = f"{err.__class__.__name__}: {err}"
                state.report_error(f"{label}: {stage.error}")
                state.status = HealthStatus.IDLE
                state.current = None
                return None
            stage.finished = time.monotonic()
            if result is None:
                stage.result = "fail"
                stage.error = "returned no result"
                state.report_error(f"{label} returned no result")
            else:
                stage.result = "ok"
                state.last = label
            state.status = HealthStatus.IDLE
            state.current = None
            return result
        return wrapper
    return decorator


@contextmanager
def track(state: HealthState, label: str):
    stage = StageMetrics(name=label, started=time.monotonic())
    state.stages.append(stage)
    try:
        yield stage
        stage.result = "ok"
    except Exception as err:
        stage.result = "fail"
        stage.error = f"{err.__class__.__name__}: {err}"
        state.report_error(f"{label}: {stage.error}")
        raise
    finally:
        stage.finished = time.monotonic()

"""
    Desc: self-healing checks and repairs for environment and modules
    Creator: Kirosha
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from based.config import config
from based.utils.__assets import discover_tests, ensure_assets, verify_test
from based.utils.__console import log_err, log_ok, log_step, log_warn
from based.utils.__llm import get_tags


@dataclass
class Check:
    name: str
    ok: bool
    reason: str | None = None
    fixed: bool = False


@dataclass
class RepairReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, check: Check) -> None:
        self.checks.append(check)

    @property
    def all_ok(self) -> bool:
        return all(c.ok or c.fixed for c in self.checks)

    def snapshot(self) -> dict:
        return {
            "all_ok": self.all_ok,
            "checks": [
                {"name": c.name, "ok": c.ok, "fixed": c.fixed, "reason": c.reason}
                for c in self.checks
            ],
        }


class Repair:
    def __init__(self) -> None:
        self.report = RepairReport()

    def run(self, fix: bool = True) -> RepairReport:
        log_step("running environment repair")
        self.__check_python()
        self.__check_ffmpeg()
        self.__check_ollama()
        self.__check_models()
        self.__check_assets()
        if fix:
            self.__fix_failed()
        return self.report

    def __check_python(self) -> None:
        version = sys.version_info[:2]
        minimum = config.min_python_version
        ok = version >= minimum
        self.report.add(Check("python", ok, None if ok else f"need >= {minimum}, got {version}"))
        (log_ok if ok else log_err)(f"python {version[0]}.{version[1]}")

    def __check_ffmpeg(self) -> None:
        path = shutil.which("ffmpeg")
        ok = path is not None
        self.report.add(Check("ffmpeg", ok, None if ok else "ffmpeg not in PATH"))
        (log_ok if ok else log_warn)("ffmpeg " + ("found" if ok else "missing"))

    def __check_ollama(self) -> None:
        tags = get_tags()
        ok = tags is not None
        self.report.add(Check("ollama", ok, None if ok else f"unreachable at {config.ollama_host}"))
        (log_ok if ok else log_err)(f"ollama {config.ollama_host}")

    def __check_models(self) -> None:
        tags = get_tags() or []
        for model in (config.text_model, config.vision_model):
            ok = any(tag.startswith(model) for tag in tags)
            self.report.add(Check(f"model {model}", ok, None if ok else f"model {model} not pulled"))
            (log_ok if ok else log_warn)(f"model {model}")

    def __check_assets(self) -> None:
        marker = config.cache_dir / "assets" / config.assets_version / ".ready"
        ok = marker.exists()
        self.report.add(Check("assets", ok, None if ok else "assets archive not extracted"))
        if not ok:
            return
        for module in ("notes", "skeds", "tasks"):
            for test in discover_tests(module):
                ok = verify_test(module, test)
                self.report.add(Check(f"assets {module}/{test}", ok, None if ok else "incomplete"))

    def __fix_failed(self) -> None:
        for check in self.report.checks:
            if check.ok or check.fixed:
                continue
            if check.name == "assets":
                log_step("repair: downloading assets")
                check.fixed = ensure_assets(force=True)
            elif check.name.startswith("model "):
                model = check.name.split(" ", 1)[1]
                log_step(f"repair: pulling model {model}")
                check.fixed = self.__pull_model(model)
            elif check.name == "ollama":
                log_warn("repair: start ollama manually and run repair again")
            elif check.name == "ffmpeg":
                log_warn("repair: install ffmpeg manually and run repair again")

    def __pull_model(self, model: str) -> bool:
        try:
            return subprocess.run(["ollama", "pull", model]).returncode == 0
        except FileNotFoundError:
            log_err("ollama not installed")
            return False


def repair(fix: bool = True) -> dict:
    return Repair().run(fix=fix).snapshot()

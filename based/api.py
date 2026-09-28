"""
    Desc: main entrypoint that scans, verifies and loads local modules
    Creator: Kirosha
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

from based.utils.__assets import discover_tests, ensure_assets, verify_test
from based.utils.__console import log_err, log_ok, log_step, log_warn

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class BasedAPI:
    def __init__(self) -> None:
        self.modules: dict[str, object] = {}
        self.failed: dict[str, str] = {}

    def load(self, skip_setup: bool = False) -> None:
        try:
            if not skip_setup:
                ensure_assets()
            for module_dir in self.__scan_modules():
                self.__load_module(module_dir, skip_setup)
        except Exception as err:
            log_err(f"load: unexpected failure: {err.__class__.__name__}: {err}")
        finally:
            if self.failed:
                log_warn(f"failed modules: {', '.join(self.failed)}")

    def close(self) -> None:
        self.modules.clear()
        self.failed.clear()

    def health(self) -> dict:
        result: dict = {}
        for name, instance in self.modules.items():
            snapshot = instance.health_check() if hasattr(instance, "health_check") else {"status": "unknown"}
            result[name] = snapshot
        for name, reason in self.failed.items():
            result[name] = {"status": "unavailable", "reason": reason}
        return result

    def __load_module(self, module_dir: Path, skip_setup: bool) -> None:
        name = module_dir.name
        try:
            log_step(f"loading module {name}")
            if not self.__verify(name):
                self.failed[name] = "missing assets"
                log_err(f"skipping {name}: missing assets")
                return
            if not skip_setup and not self.__run_script(module_dir, "setup.py"):
                self.failed[name] = "setup failed"
                return
            if not self.__run_script(module_dir, "test.py"):
                self.failed[name] = "test failed"
                return
            instance = self.__instantiate(name)
            if instance is None:
                self.failed[name] = "instantiation failed"
                return
            setattr(self, name, instance)
            self.modules[name] = instance
            log_ok(f"module {name} loaded")
        except Exception as err:
            self.failed[name] = f"unexpected: {err.__class__.__name__}: {err}"
            log_err(f"{name}: {self.failed[name]}")

    def __scan_modules(self) -> list[Path]:
        modules_dir = Path(__file__).parent / "modules"
        if not modules_dir.exists():
            return []
        return sorted(p for p in modules_dir.iterdir() if p.is_dir() and not p.name.startswith("_"))

    def __verify(self, name: str) -> bool:
        for test in discover_tests(name):
            if not verify_test(name, test):
                return False
        return True

    def __run_script(self, module_dir: Path, script_name: str) -> bool:
        script = module_dir / "deploy" / script_name
        if not script.exists():
            log_warn(f"{module_dir.name}: deploy/{script_name} not found, skipping")
            return True
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + existing if existing else "")
        try:
            result = subprocess.run([sys.executable, str(script)], cwd=str(PROJECT_ROOT), env=env)
        except Exception as err:
            log_err(f"{module_dir.name}: {script_name} subprocess failed: {err.__class__.__name__}: {err}")
            return False
        return result.returncode == 0

    def __instantiate(self, name: str) -> object | None:
        try:
            module = importlib.import_module(f"based.modules.{name}.api")
            cls = getattr(module, f"{name.capitalize()}API")
            return cls()
        except Exception as err:
            return log_err(f"failed to instantiate module {name}: {err.__class__.__name__}: {err}")

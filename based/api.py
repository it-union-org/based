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
        self.metrics: dict = {
            "total_seconds": 0.0,
            "assets_seconds": 0.0,
            "modules": {},
        }

    def load(self, skip_setup: bool = False) -> None:
        import time

        started_total = time.monotonic()
        try:
            if not skip_setup:
                started_assets = time.monotonic()
                ensure_assets()
                self.metrics["assets_seconds"] = round(time.monotonic() - started_assets, 3)
            for module_dir in self.__scan_modules():
                self.__load_module(module_dir, skip_setup)
        except Exception as err:
            log_err(f"load: unexpected failure: {err.__class__.__name__}: {err}")
        finally:
            self.metrics["total_seconds"] = round(time.monotonic() - started_total, 3)
            if self.failed:
                log_warn(f"failed modules: {', '.join(self.failed)}")
            self.__print_metrics()

    def close(self) -> None:
        self.modules.clear()
        self.failed.clear()
        self.metrics = {"total_seconds": 0.0, "assets_seconds": 0.0, "modules": {}}

    def health(self) -> dict:
        result: dict = {}
        for name, instance in self.modules.items():
            snapshot = instance.health_check() if hasattr(instance, "health_check") else {"status": "unknown"}
            result[name] = snapshot
        for name, reason in self.failed.items():
            result[name] = {"status": "unavailable", "reason": reason}
        return result

    def timings(self) -> dict:
        """Возвращает метрики времени по стадиям и суммарные."""
        return dict(self.metrics)

    def __print_metrics(self) -> None:
        from based.utils.__console import print_table

        rows = {
            "assets": f"{self.metrics['assets_seconds']:.3f}s",
            "total": f"{self.metrics['total_seconds']:.3f}s",
        }
        for name, m in self.metrics["modules"].items():
            status = m.get("status", "?")
            rows[f"{name} status"] = status
            rows[f"{name} verify"] = f"{m.get('verify_seconds', 0):.3f}s"
            rows[f"{name} setup"] = f"{m.get('setup_seconds', 0):.3f}s"
            rows[f"{name} test"] = f"{m.get('test_seconds', 0):.3f}s"
            rows[f"{name} instantiate"] = f"{m.get('instantiate_seconds', 0):.3f}s"
            rows[f"{name} total"] = f"{m.get('total_seconds', 0):.3f}s"
        print_table("based load timings", rows)

    def __load_module(self, module_dir: Path, skip_setup: bool) -> None:
        import time

        name = module_dir.name
        started = time.monotonic()
        module_metrics: dict = {"status": "ok"}

        def stage(label: str, started_at: float) -> None:
            module_metrics[f"{label}_seconds"] = round(time.monotonic() - started_at, 3)

        try:
            log_step(f"loading module {name}")

            started_verify = time.monotonic()
            if not self.__verify(name):
                stage("verify", started_verify)
                module_metrics["status"] = "missing assets"
                self.failed[name] = "missing assets"
                log_err(f"skipping {name}: missing assets")
                return
            stage("verify", started_verify)

            if not skip_setup:
                started_setup = time.monotonic()
                if not self.__run_script(module_dir, "setup.py"):
                    stage("setup", started_setup)
                    module_metrics["status"] = "setup failed"
                    self.failed[name] = "setup failed"
                    return
                stage("setup", started_setup)
            else:
                module_metrics["setup_seconds"] = 0.0

            started_test = time.monotonic()
            if not self.__run_script(module_dir, "test.py"):
                stage("test", started_test)
                module_metrics["status"] = "test failed"
                self.failed[name] = "test failed"
                return
            stage("test", started_test)

            started_instantiate = time.monotonic()
            instance = self.__instantiate(name)
            stage("instantiate", started_instantiate)

            if instance is None:
                module_metrics["status"] = "instantiation failed"
                self.failed[name] = "instantiation failed"
                return

            setattr(self, name, instance)
            self.modules[name] = instance
            log_ok(f"module {name} loaded")
        except Exception as err:
            module_metrics["status"] = "unexpected"
            module_metrics["error"] = f"{err.__class__.__name__}: {err}"
            self.failed[name] = f"unexpected: {err.__class__.__name__}: {err}"
            log_err(f"{name}: {self.failed[name]}")
        finally:
            module_metrics["total_seconds"] = round(time.monotonic() - started, 3)
            self.metrics["modules"][name] = module_metrics

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

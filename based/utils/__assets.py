"""
    Desc: downloads the assets archive and resolves prompts, tests and runs
    Creator: Kirosha
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import httpx

from based.config import config
from based.utils.__console import log_err, log_ok, log_step, log_warn

ARCHIVE_NAME = "assets.zip"
ARCHIVE_ROOT = "modules"


def cache_root(version: str | None = None) -> Path:
    return config.cache_dir / "assets" / (version or config.assets_version)


def module_dir(module: str, version: str | None = None) -> Path:
    return cache_root(version) / ARCHIVE_ROOT / module


def prompts_dir(module: str, version: str | None = None) -> Path:
    return module_dir(module, version) / "prompts"


def tests_dir(module: str, version: str | None = None) -> Path:
    return module_dir(module, version) / "tests"


def test_dir(module: str, test: str, version: str | None = None) -> Path:
    return tests_dir(module, version) / test


def _natural_key(name: str) -> tuple:
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in name.split("_"))


def ensure_assets(version: str | None = None, force: bool = False) -> bool:
    version = version or config.assets_version
    root = cache_root(version)
    marker = root / ".ready"
    if marker.exists() and not force:
        log_ok("assets ready")
        return True

    url = f"{config.assets_base_url}/{version}/{ARCHIVE_NAME}"
    if not url.startswith("http"):
        log_err(f"invalid assets url: {url}")
        return False

    root.mkdir(parents=True, exist_ok=True)
    archive = root / ARCHIVE_NAME
    log_step(f"downloading assets: {url}")
    try:
        with httpx.Client(timeout=config.assets_download_timeout, follow_redirects=True) as client:
            response = client.get(url)
    except httpx.HTTPError as err:
        log_err(f"assets download failed: {err.__class__.__name__}: {err}")
        return False

    if response.status_code != 200:
        log_err(f"assets download failed, status {response.status_code}: {response.text[:config.assets_error_body_limit]}")
        return False
    if "text/html" in response.headers.get("content-type", ""):
        log_err(f"assets url returned html instead of an archive: {url}")
        return False

    archive.write_bytes(response.content)
    if not archive.exists() or archive.stat().st_size == 0:
        log_err(f"assets archive was not written: {archive}")
        return False
    log_ok(f"downloaded {archive.stat().st_size} bytes to {archive}")

    target_root = root / ARCHIVE_ROOT
    shutil.rmtree(target_root, ignore_errors=True)
    marker.unlink(missing_ok=True)

    prefix = f"{ARCHIVE_ROOT}/"
    extracted = 0
    try:
        with zipfile.ZipFile(archive) as archive_zip:
            for info in archive_zip.infolist():
                if info.is_dir() or not info.filename.startswith(prefix):
                    continue
                destination = (root / info.filename).resolve()
                if not destination.is_relative_to(target_root.resolve()):
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive_zip.read(info))
                extracted += 1
    except zipfile.BadZipFile:
        log_err(f"assets archive is not a valid zip: {archive}")
        return False

    if extracted == 0:
        log_err(f"assets archive has no {prefix} entries: {archive}")
        return False

    archive.unlink(missing_ok=True)
    marker.touch()
    log_ok(f"assets extracted ({version})")
    return True


def discover_tests(module: str, version: str | None = None) -> list[str]:
    base = tests_dir(module, version)
    if not base.exists():
        return []
    names = [p.name for p in base.iterdir() if p.is_dir() and p.name.startswith("test_")]
    return sorted(names, key=_natural_key)


def verify_test(module: str, test: str, version: str | None = None) -> bool:
    base = tests_dir(module, version)
    if not base.exists():
        return True
    path = test_dir(module, test, version)
    if not path.exists():
        log_warn(f"{module} {test}: test directory is missing")
        return False
    if not any(p.is_file() for p in path.rglob("*")) and prompts_dir(module, version).exists():
        log_warn(f"{module} {test}: test directory has no files")
        return False
    return True


def bundle(module: str, test: str, version: str | None = None) -> dict[str, list[Path]]:
    base = test_dir(module, test, version)
    result: dict[str, list[Path]] = {}
    if not base.exists():
        return result
    loose = sorted(p for p in base.iterdir() if p.is_file())
    if loose:
        result["files"] = loose
    for subdir in sorted(p for p in base.iterdir() if p.is_dir()):
        result[subdir.name] = sorted(p for p in subdir.iterdir() if p.is_file())
    return result


def _runs(module: str) -> list[Path]:
    runs_dir = config.cache_dir / module
    if not runs_dir.exists():
        return []
    runs = [p for p in runs_dir.iterdir() if p.is_dir()]
    return sorted(runs, key=lambda p: p.stat().st_mtime, reverse=True)


def clear_runs(module: str, keep: int = 0) -> None:
    if not (config.cache_dir / module).exists():
        return
    stale = _runs(module)[keep:]
    for run in stale:
        shutil.rmtree(run, ignore_errors=True)
    log_step(f"cleared {len(stale)} old runs for {module}")


def latest_run(module: str) -> Path | None:
    runs = _runs(module)
    return runs[0] if runs else None

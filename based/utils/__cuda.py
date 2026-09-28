"""
    Desc: cuda detection and windows nvidia dll registration
    Creator: Kirosha
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_NVIDIA_PATTERNS = ("cublas64_*.dll", "cublasLt64_*.dll", "cudnn*.dll", "nvrtc64_*.dll")


def _nvidia_root() -> Path | None:
    try:
        import nvidia
    except ImportError:
        return None
    for entry in getattr(nvidia, "__path__", []) or []:
        candidate = Path(entry)
        if candidate.exists():
            return candidate
    return None


def _dll_dirs() -> list[Path]:
    root = _nvidia_root()
    if root is None:
        return []
    dirs: set[Path] = set()
    for pattern in _NVIDIA_PATTERNS:
        for dll in root.rglob(pattern):
            dirs.add(dll.parent)
    return sorted(dirs)


def has_cuda() -> bool:
    try:
        import ctranslate2
    except ImportError:
        return False
    try:
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def register_dll_directories() -> None:
    if sys.platform != "win32":
        return
    dirs = _dll_dirs()
    if not dirs:
        return
    for dll_dir in dirs:
        try:
            os.add_dll_directory(str(dll_dir))
        except Exception:
            pass
    extra = os.pathsep.join(str(d) for d in dirs)
    current = os.environ.get("PATH", "")
    os.environ["PATH"] = extra + os.pathsep + current if current else extra

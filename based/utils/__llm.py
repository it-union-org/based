"""
    Desc: unified ollama client with retries, timeouts and image normalization
    Creator: Kirosha
"""

from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from pathlib import Path

import httpx

from based.config import config
from based.utils.__console import log_err, log_ok, log_step, log_warn
from based.utils.__cuda import has_cuda, register_dll_directories

_whisper_model = None
_whisper_device = "cpu"
_last_error: str | None = None

_CJK_RANGES = (
    (0x4E00, 0x9FFF),
    (0x3040, 0x30FF),
    (0xAC00, 0xD7AF),
    (0x0600, 0x06FF),
)


def last_error() -> str | None:
    return _last_error


def _fail(msg: str) -> None:
    global _last_error
    _last_error = msg
    return log_err(msg)


def _has_non_cyrillic(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        for start, end in _CJK_RANGES:
            if start <= code <= end:
                return True
    return False


def _image_info(image_path: Path) -> str:
    resolution = "unknown"
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            resolution = f"{img.width}x{img.height}"
    except Exception:
        pass
    try:
        size = image_path.stat().st_size
    except OSError:
        size = 0
    return f"{image_path.name} {resolution} {size} bytes"


def _normalize_image(image_path: Path) -> bytes:
    try:
        from PIL import Image
    except ImportError:
        return image_path.read_bytes()
    img = Image.open(image_path).convert("RGB")
    longest = max(img.size)
    if longest > config.vision_max_image_side:
        ratio = config.vision_max_image_side / longest
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=config.vision_jpeg_quality)
    return buffer.getvalue()


async def _chat(payload: dict) -> str | None:
    global _last_error
    _last_error = None
    url = f"{config.ollama_host}/api/chat"
    model = payload.get("model")
    reason = "no attempts made"
    async with httpx.AsyncClient(timeout=config.llm_request_timeout) as client:
        for attempt in range(1, config.llm_max_retries + 1):
            where = f"attempt {attempt}/{config.llm_max_retries}, model={model}, endpoint={url}"
            try:
                response = await client.post(url, json=payload)
            except httpx.HTTPError as err:
                reason = f"transport {err.__class__.__name__}: {err} ({where})"
                log_warn(f"ollama {reason}")
                await asyncio.sleep(config.llm_retry_sleep)
                continue
            if response.status_code != 200:
                reason = f"http {response.status_code}: {response.text[:config.llm_error_body_limit]} ({where})"
                log_warn(f"ollama {reason}")
                await asyncio.sleep(config.llm_retry_sleep)
                continue
            try:
                content = response.json().get("message", {}).get("content")
            except ValueError as err:
                reason = f"invalid json: {err} ({where})"
                log_warn(f"ollama {reason}")
                await asyncio.sleep(config.llm_retry_sleep)
                continue
            if content:
                return content
            reason = f"empty content ({where})"
            log_warn(f"ollama {reason}")
            await asyncio.sleep(config.llm_retry_sleep)
    return _fail(f"ollama request failed after {config.llm_max_retries} retries, model={model}: {reason}")


async def ask_text(system: str, user: str) -> str | None:
    return await _chat(
        {
            "model": config.text_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "num_ctx": config.text_num_ctx,
                "num_predict": config.text_num_predict,
            },
        }
    )


async def ask_vision(system: str, image_path: Path) -> str | None:
    try:
        raw = _normalize_image(image_path)
    except Exception as err:
        return _fail(f"vision {_image_info(image_path)}: image preparation failed: {err}")
    payload = {
        "model": config.vision_model,
        "messages": [
            {
                "role": "user",
                "content": system,
                "images": [base64.b64encode(raw).decode("utf-8")],
            }
        ],
        "stream": False,
        "options": {
            "num_ctx": config.vision_num_ctx,
            "num_predict": config.vision_num_predict,
        },
    }
    result = await _chat(payload)
    if result is None:
        return _fail(f"vision {_image_info(image_path)}: {_last_error}")
    return result


def get_tags() -> list[str] | None:
    url = f"{config.ollama_host}/api/tags"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as err:
        return log_err(f"failed to fetch ollama tags from {url}: {err.__class__.__name__}: {err}")
    return [model["name"] for model in response.json().get("models", [])]


async def transcribe(audio_path: Path) -> str | None:
    def _run() -> str | None:
        global _whisper_model, _whisper_device
        if _whisper_model is None:
            register_dll_directories()
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                return _fail("faster-whisper not installed, install based[notes]")
            configured = config.whisper_device
            if configured in ("cuda", "cpu"):
                device = configured
            else:
                device = "cuda" if has_cuda() else "cpu"
            log_step(f"whisper device: {device}")
            try:
                _whisper_model = WhisperModel(config.whisper_model, device=device)
                _whisper_device = device
                log_ok(f"whisper model loaded on {device}")
            except Exception as err:
                log_warn(f"whisper {device} init failed ({err.__class__.__name__}: {err}), falling back to cpu")
                try:
                    _whisper_model = WhisperModel(config.whisper_model, device="cpu", compute_type="int8")
                    _whisper_device = "cpu"
                    log_ok("whisper model loaded on cpu (fallback)")
                except Exception as err2:
                    return _fail(f"whisper cpu init failed: {err2.__class__.__name__}: {err2}")
        try:
            segments, info = _whisper_model.transcribe(
                str(audio_path),
                language=config.whisper_language,
                vad_filter=config.whisper_vad_filter,
                beam_size=config.whisper_beam_size,
                without_timestamps=True,
                condition_on_previous_text=False,
            )
            parts = []
            skipped = 0
            for index, segment in enumerate(segments):
                if index % config.whisper_progress_every == 0:
                    log_step(f"whisper progress: {segment.end:.0f}s / {info.duration:.0f}s")
                text = segment.text.strip()
                if not text:
                    continue
                if _has_non_cyrillic(text):
                    skipped += 1
                    continue
                parts.append(text)
            if skipped:
                log_warn(f"whisper skipped {skipped} non-russian segment(s) in {audio_path.name}")
            text = " ".join(parts)
        except Exception as err:
            return _fail(
                f"whisper transcribe failed for {audio_path.name} on {_whisper_device}: "
                f"{err.__class__.__name__}: {err}"
            )
        if not text:
            return _fail(f"whisper produced an empty transcript for {audio_path.name}")
        return text
    return await asyncio.to_thread(_run)


def unload_models() -> None:
    url = f"{config.ollama_host}/api/generate"
    for model in (config.text_model, config.vision_model):
        try:
            httpx.post(url, json={"model": model, "keep_alive": 0}, timeout=10.0)
        except httpx.HTTPError:
            pass

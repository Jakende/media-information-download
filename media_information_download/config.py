from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
SUPPORTED_MEDIA_EXTENSIONS = {
    ".aac",
    ".avi",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
    ".wma",
}
SUPPORTED_MEDIA_MIME_PREFIXES = ("audio/", "video/")


def get_output_dir() -> Path:
    output_dir = os.environ.get("MEDIA_OUTPUT_DIR") or os.environ.get("YTDL_OUTPUT_DIR")
    path = Path(output_dir).expanduser() if output_dir else DEFAULT_OUTPUT_DIR
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_model_name() -> str:
    return (os.environ.get("WHISPER_MODEL") or "large").strip() or "large"


def get_whisper_language() -> str | None:
    language = (os.environ.get("WHISPER_LANGUAGE") or "").strip()
    return language or None


def get_cookies_from_browser() -> tuple[str, ...] | None:
    browser = os.environ.get("YTDL_COOKIES_FROM_BROWSER", "").strip()
    if not browser:
        return None

    parts = [part.strip() for part in browser.split(":", maxsplit=1) if part.strip()]
    return tuple(parts) if parts else None


def is_project_venv_active() -> bool:
    active_prefix = Path(sys.prefix).resolve()
    project_venv = (PROJECT_ROOT / ".venv").resolve()
    return active_prefix == project_venv or project_venv in active_prefix.parents


def dependency_status(include_transcription: bool = True) -> list[str]:
    messages: list[str] = []
    if not is_project_venv_active():
        messages.append(
            f"Python is not running from the project venv: expected {PROJECT_ROOT / '.venv'}"
        )

    if shutil.which("ffmpeg") is None:
        messages.append("ffmpeg is not available on PATH.")

    try:
        import yt_dlp  # noqa: F401
    except Exception:
        messages.append("Python package 'yt-dlp' is not installed in the active environment.")

    if include_transcription:
        try:
            import torch  # noqa: F401
            import whisper  # noqa: F401
        except Exception:
            messages.append(
                "Whisper dependencies are missing. Install local deps with: "
                ". .venv/bin/activate && pip install -r requirements-transcribe.txt"
            )

    return messages


def require_dependencies(include_transcription: bool = True) -> None:
    messages = dependency_status(include_transcription=include_transcription)
    if messages:
        raise RuntimeError("\n".join(messages))

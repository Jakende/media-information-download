from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class MediaItem:
    source_type: str
    source_url: str
    media_url: str
    title: str
    mime_type: str = ""
    published: str = ""
    description: str = ""


@dataclass
class ProcessedMedia:
    item: MediaItem
    downloaded_path: Path | None = None
    mp3_path: Path | None = None
    transcript_path: Path | None = None
    error: str | None = None
    notes: list[str] = field(default_factory=list)


ProgressCallback = Callable[[str], None]

from __future__ import annotations

import mimetypes
import re
import urllib.parse
import urllib.request
from pathlib import Path

from media_information_download.models import MediaItem


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._() -]+")


def safe_filename(value: str, fallback: str = "media") -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", value).strip(" ._")
    return cleaned or fallback


def _extension_from_item(item: MediaItem, response_url: str) -> str:
    path_suffix = Path(urllib.parse.urlparse(response_url).path).suffix
    if path_suffix:
        return path_suffix

    guessed = mimetypes.guess_extension(item.mime_type.split(";", maxsplit=1)[0].strip())
    return guessed or ".media"


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path

    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create unique output path for {path}")


class HTTPDownloader:
    def download(self, item: MediaItem, output_dir: Path) -> Path:
        request = urllib.request.Request(
            item.media_url,
            headers={"User-Agent": "media-information-download/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            extension = _extension_from_item(item, response.geturl())
            target = _dedupe_path(output_dir / f"{safe_filename(item.title)}{extension}")
            with target.open("wb") as file:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    file.write(chunk)

        return target

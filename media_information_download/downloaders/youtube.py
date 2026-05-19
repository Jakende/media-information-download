from __future__ import annotations

from pathlib import Path
from typing import Any

from media_information_download.config import get_cookies_from_browser
from media_information_download.models import MediaItem

try:
    import yt_dlp  # type: ignore
except Exception:  # pragma: no cover - checked at runtime
    yt_dlp = None


def _build_ydl_opts(output_dir: Path, format_selector: str) -> dict[str, Any]:
    ydl_opts: dict[str, Any] = {
        "format": format_selector,
        "merge_output_format": "mp4",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
        "fragment_retries": 10,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "web"],
            }
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            )
        },
    }

    cookies_from_browser = get_cookies_from_browser()
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = cookies_from_browser

    return ydl_opts


def _resolve_downloaded_path(output_dir: Path, prepared_filename: Path) -> Path:
    if prepared_filename.exists():
        return prepared_filename

    stem = prepared_filename.stem
    matches = sorted(
        path
        for path in output_dir.glob(f"{stem}.*")
        if path.suffix.lower() not in {".part", ".ytdl"}
    )
    if matches:
        return matches[0]

    return prepared_filename


class YouTubeDownloader:
    def download(self, item: MediaItem, output_dir: Path) -> Path:
        if yt_dlp is None:
            raise RuntimeError("Python package 'yt-dlp' is not installed.")

        format_attempts = [
            ("bv*+ba/b", "best split video/audio streams"),
            ("best[ext=mp4]/best", "progressive MP4 fallback"),
        ]
        last_error: Exception | None = None

        for format_selector, description in format_attempts:
            try:
                ydl_opts = _build_ydl_opts(output_dir, format_selector)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(item.media_url, download=True)
                    filename = Path(ydl.prepare_filename(info))
                return _resolve_downloaded_path(output_dir, filename)
            except Exception as exc:
                last_error = exc
                if "HTTP Error 403" not in str(exc):
                    raise
                if description == format_attempts[-1][1]:
                    break

        if last_error is not None:
            raise last_error
        raise RuntimeError("YouTube download failed without a captured exception.")

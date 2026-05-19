from __future__ import annotations

import re

from media_information_download.models import MediaItem


YOUTUBE_URL_RE = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]{6,}.*$",
    re.IGNORECASE,
)


def validate_url(url: str) -> bool:
    return bool(YOUTUBE_URL_RE.match(url.strip()))


def parse_urls(raw_value: str) -> list[str]:
    return [part.strip() for part in raw_value.split(",") if part.strip()]


class YouTubeSource:
    name = "youtube"

    def collect(self, raw_value: str) -> list[MediaItem]:
        urls = parse_urls(raw_value)
        invalid_urls = [url for url in urls if not validate_url(url)]
        if invalid_urls:
            raise ValueError(
                "Invalid YouTube URL(s): " + ", ".join(invalid_urls)
            )

        return [
            MediaItem(
                source_type=self.name,
                source_url=url,
                media_url=url,
                title="YouTube media",
            )
            for url in urls
        ]

from __future__ import annotations

import mimetypes
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from media_information_download.config import (
    SUPPORTED_MEDIA_EXTENSIONS,
    SUPPORTED_MEDIA_MIME_PREFIXES,
)
from media_information_download.models import MediaItem


def _tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", maxsplit=1)[-1].lower()


def _child_text(element: ET.Element, names: set[str]) -> str:
    for child in element:
        if _tag_name(child) in names and child.text:
            return child.text.strip()
    return ""


def _is_supported_media(url: str, mime_type: str = "") -> bool:
    clean_path = urllib.parse.urlparse(url).path
    extension = mimetypes.guess_extension(mime_type.split(";", maxsplit=1)[0].strip())
    suffix = (extension or "").lower() or clean_path.lower().rsplit(".", maxsplit=1)[-1]
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix}"

    if suffix in SUPPORTED_MEDIA_EXTENSIONS:
        return True

    mime = mime_type.lower().strip()
    return any(mime.startswith(prefix) for prefix in SUPPORTED_MEDIA_MIME_PREFIXES)


def _first_attr(element: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        value = element.attrib.get(name)
        if value:
            return value.strip()
    return ""


def parse_feed_xml(feed_xml: bytes | str, feed_url: str) -> list[MediaItem]:
    root = ET.fromstring(feed_xml)
    candidates = [
        element
        for element in root.iter()
        if _tag_name(element) in {"item", "entry"}
    ]

    items: list[MediaItem] = []
    for entry in candidates:
        title = _child_text(entry, {"title"}) or "RSS media item"
        published = _child_text(entry, {"pubdate", "published", "updated"})
        description = _child_text(entry, {"description", "summary", "subtitle"})

        media_candidates: list[tuple[str, str]] = []
        for child in entry.iter():
            name = _tag_name(child)
            if name == "enclosure":
                media_candidates.append(
                    (
                        _first_attr(child, ("url", "href")),
                        _first_attr(child, ("type", "medium")),
                    )
                )
            elif name in {"content", "player"} and (
                "media" in child.tag.lower() or child.attrib.get("url")
            ):
                media_candidates.append(
                    (
                        _first_attr(child, ("url", "href")),
                        _first_attr(child, ("type", "medium")),
                    )
                )
            elif name == "link":
                href = _first_attr(child, ("href", "url"))
                link_type = _first_attr(child, ("type",))
                if href and (link_type or _is_supported_media(href)):
                    media_candidates.append((href, link_type))
                elif child.text and _is_supported_media(child.text.strip()):
                    media_candidates.append((child.text.strip(), ""))

        for media_url, mime_type in media_candidates:
            if not media_url:
                continue
            media_url = urllib.parse.urljoin(feed_url, media_url)
            if not _is_supported_media(media_url, mime_type):
                continue
            items.append(
                MediaItem(
                    source_type="rss",
                    source_url=feed_url,
                    media_url=media_url,
                    title=title,
                    mime_type=mime_type,
                    published=published,
                    description=description,
                )
            )
            break

    return items


class RSSSource:
    name = "rss"

    def collect(self, feed_url: str) -> list[MediaItem]:
        parsed = urllib.parse.urlparse(feed_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("RSS feed URL must start with http:// or https://")

        request = urllib.request.Request(
            feed_url,
            headers={
                "User-Agent": "media-information-download/1.0",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            feed_xml = response.read()

        items = parse_feed_xml(feed_xml, feed_url)
        if not items:
            raise ValueError("No supported audio or video enclosures were found in the RSS feed.")
        return items

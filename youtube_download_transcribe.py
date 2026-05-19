#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from media_information_download.config import get_model_name, get_output_dir, get_whisper_language
from media_information_download.pipeline import MediaPipeline, ProcessOptions
from media_information_download.sources.youtube import parse_urls, validate_url


def print_error(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download YouTube video, extract MP3, transcribe to Markdown.")
    parser.add_argument(
        "--url",
        default="",
        help="One or more YouTube URLs, comma-separated.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between batch entries. Default: 2.0",
    )
    parser.add_argument("--model", default="", help="Whisper model name. Defaults to WHISPER_MODEL or large.")
    parser.add_argument("--language", default=None, help="Optional Whisper language code. Defaults to auto.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_urls = args.url.strip()
    if not raw_urls:
        if sys.stdin.isatty():
            raw_urls = input("YouTube URL(s), comma-separated: ").strip()
        else:
            print_error("No URL provided. Use: python3 youtube_download_transcribe.py --url <URL1,URL2,...>")
            return 1

    urls = parse_urls(raw_urls)
    invalid_urls = [url for url in urls if not validate_url(url)]
    if not urls or invalid_urls:
        for invalid_url in invalid_urls:
            print_error(f"Invalid YouTube URL: {invalid_url}")
        return 1

    pipeline = MediaPipeline(progress=lambda message: print(message, flush=True))
    results = pipeline.process(
        ProcessOptions(
            source_type="youtube",
            raw_input=raw_urls,
            output_dir=get_output_dir(),
            transcribe=True,
            model_name=args.model or get_model_name(),
            language=args.language if args.language is not None else get_whisper_language(),
            delay_seconds=args.delay,
        )
    )
    return 1 if any(result.error for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

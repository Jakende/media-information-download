from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from media_information_download.config import (
    dependency_status,
    get_model_name,
    get_output_dir,
    get_whisper_language,
)
from media_information_download.output import list_output_files
from media_information_download.pipeline import MediaPipeline, ProcessOptions


class Style:
    reset = "\033[0m"
    dim = "\033[2m"
    bold = "\033[1m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    blue = "\033[34m"
    magenta = "\033[35m"


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _color(value: str, style: str) -> str:
    if not _supports_color():
        return value
    return f"{style}{value}{Style.reset}"


def _terminal_width() -> int:
    return min(96, max(64, shutil.get_terminal_size((88, 24)).columns))


def _rule(label: str = "") -> str:
    width = _terminal_width()
    if not label:
        return _color("-" * width, Style.dim)
    text = f" {label} "
    left = max(2, (width - len(text)) // 2)
    right = max(2, width - left - len(text))
    return _color("-" * left + text + "-" * right, Style.dim)


def _banner() -> None:
    width = _terminal_width()
    title = "MEDIA INFORMATION DOWNLOAD"
    subtitle = "YouTube + RSS -> MP3 -> Whisper Markdown"
    print(_color("=" * width, Style.cyan))
    print(_color(title.center(width), Style.bold + Style.cyan))
    print(_color(subtitle.center(width), Style.dim))
    print(_color("=" * width, Style.cyan))


def _prompt(label: str) -> str:
    return input(_color(f"{label} ", Style.bold + Style.blue)).strip()


def _print_progress(message: str) -> None:
    prefix = _color(">", Style.cyan)
    if message.startswith("ERROR"):
        prefix = _color("!", Style.red)
        message = _color(message, Style.red)
    elif "written" in message.lower() or "ready" in message.lower() or "downloaded" in message.lower():
        prefix = _color("+", Style.green)
    print(f"  {prefix} {message}", flush=True)


def _yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = _prompt(f"{prompt} [{suffix}]:").lower()
    if not answer:
        return default
    return answer in {"y", "yes", "j", "ja"}


def _print_results(results) -> None:
    print("\n" + _rule("Results"))
    for result in results:
        title = result.item.title
        if result.error:
            print(f"{_color('x', Style.red)} {title}: {_color(result.error, Style.red)}")
            for note in result.notes:
                print(f"  {_color(note, Style.yellow)}")
            continue
        print(f"{_color('+', Style.green)} {_color(title, Style.bold)}")
        if result.downloaded_path:
            print(f"  {_color('media', Style.dim)}      {result.downloaded_path}")
        if result.mp3_path:
            print(f"  {_color('mp3', Style.dim)}        {result.mp3_path}")
        if result.transcript_path:
            print(f"  {_color('transcript', Style.dim)} {result.transcript_path}")


def _process_source(source_type: str) -> None:
    label = "YouTube URL(s)" if source_type == "youtube" else "RSS feed URL"
    print("\n" + _rule(label))
    raw_input = _prompt(f"{label}:")
    if not raw_input:
        print(_color("No input provided.", Style.yellow))
        return

    transcribe = _yes_no("Run transcription after download", default=True)
    model_name = get_model_name()
    language = get_whisper_language()
    if transcribe:
        custom_model = _prompt(f"Whisper model [{model_name}]:")
        if custom_model:
            model_name = custom_model
        custom_language = _prompt(f"Language code, empty for auto [{language or 'auto'}]:")
        language = custom_language or language

    pipeline = MediaPipeline(progress=_print_progress)
    results = pipeline.process(
        ProcessOptions(
            source_type=source_type,
            raw_input=raw_input,
            output_dir=get_output_dir(),
            transcribe=transcribe,
            model_name=model_name,
            language=language,
        )
    )
    _print_results(results)


def _transcribe_existing() -> None:
    output_dir = get_output_dir()
    candidates = [
        path
        for path in list_output_files(output_dir)
        if path.suffix.lower() in {".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg"}
    ]
    if not candidates:
        print(_color(f"No supported audio files found in {output_dir}", Style.yellow))
        return

    print("\n" + _rule("Audio Files"))
    for index, path in enumerate(candidates, start=1):
        print(f"{_color(str(index).rjust(2), Style.cyan)}  {path.name}")
    raw_selection = _prompt("Select numbers, comma-separated, or 'all':").lower()
    if raw_selection == "all":
        selected = candidates
    else:
        selected = []
        for part in raw_selection.split(","):
            try:
                selected.append(candidates[int(part.strip()) - 1])
            except Exception:
                print(_color(f"Ignoring invalid selection: {part}", Style.yellow))
    if not selected:
        print(_color("No files selected.", Style.yellow))
        return

    pipeline = MediaPipeline(progress=_print_progress)
    results = pipeline.transcribe_existing(selected, output_dir=output_dir)
    _print_results(results)


def _show_outputs() -> None:
    output_dir = get_output_dir()
    files = list_output_files(output_dir)
    if not files:
        print(_color(f"No output files in {output_dir}", Style.yellow))
        return

    print("\n" + _rule("Output Files"))
    print(_color(str(output_dir), Style.dim))
    for path in files:
        print(f"{_color('-', Style.cyan)} {path.name}")

    if sys.platform == "darwin" and _yes_no("Open output folder in Finder", default=False):
        subprocess.run(["open", str(output_dir)], check=False)


def run_tui() -> int:
    _banner()
    print(f"{_color('Output', Style.dim)} {get_output_dir()}")
    status = dependency_status(include_transcription=False)
    if status:
        print("\n" + _rule("Environment Warnings"))
        for message in status:
            print(f"{_color('!', Style.yellow)} {message}")
        print(_color("Use ./run.sh so Python dependencies come from the local project venv.", Style.yellow))

    while True:
        try:
            print("\n" + _rule("Menu"))
            print(f"{_color('1', Style.cyan)}  Process YouTube URL")
            print(f"{_color('2', Style.cyan)}  Process RSS feed URL")
            print(f"{_color('3', Style.cyan)}  Transcribe existing audio from output")
            print(f"{_color('4', Style.cyan)}  View output files")
            print(f"{_color('5', Style.cyan)}  Quit")
            choice = _prompt("Choose:")
            if choice == "1":
                _process_source("youtube")
            elif choice == "2":
                _process_source("rss")
            elif choice == "3":
                _transcribe_existing()
            elif choice == "4":
                _show_outputs()
            elif choice == "5":
                print(_color("Done.", Style.green))
                return 0
            else:
                print(_color("Unknown option.", Style.yellow))
        except KeyboardInterrupt:
            print(_color("\nInterrupted.", Style.yellow))
        except EOFError:
            print()
            return 0
        except Exception as exc:
            print(_color(f"ERROR: {exc}", Style.red))


def run_non_interactive(args: argparse.Namespace) -> int:
    pipeline = MediaPipeline(progress=_print_progress)
    results = pipeline.process(
        ProcessOptions(
            source_type=args.source,
            raw_input=args.url,
            output_dir=get_output_dir(),
            transcribe=not args.no_transcribe,
            model_name=args.model or get_model_name(),
            language=args.language if args.language is not None else get_whisper_language(),
            delay_seconds=args.delay,
        )
    )
    _print_results(results)
    return 1 if any(result.error for result in results) else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download media from YouTube or RSS and transcribe it.")
    parser.add_argument("--source", choices=("youtube", "rss"), help="Input source type.")
    parser.add_argument("--url", help="YouTube URL(s) or RSS feed URL.")
    parser.add_argument("--no-transcribe", action="store_true", help="Download and convert to MP3 only.")
    parser.add_argument("--model", help="Whisper model name. Defaults to WHISPER_MODEL or large.")
    parser.add_argument("--language", help="Optional Whisper language code. Empty/default means auto.")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between batch items.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.source or args.url:
        if not args.source or not args.url:
            print("--source and --url must be provided together.", file=sys.stderr)
            return 2
        return run_non_interactive(args)
    return run_tui()


if __name__ == "__main__":
    raise SystemExit(main())

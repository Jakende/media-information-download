from __future__ import annotations

import argparse
import os
import select
import shutil
import subprocess
import sys
import termios
import tty
from pathlib import Path

from media_information_download.config import (
    dependency_status,
    get_model_name,
    get_output_dir,
    get_whisper_language,
)
from media_information_download.output import list_output_files
from media_information_download.pipeline import MediaPipeline, ProcessOptions


BACK = "__back__"
ESCAPE = "__escape__"
ENTER = "__enter__"
UP = "__up__"
DOWN = "__down__"

MODEL_OPTIONS = ["tiny", "base", "small", "medium", "large"]
LANGUAGE_OPTIONS: list[tuple[str, str | None]] = [
    ("Auto detect", None),
    ("German", "de"),
    ("English", "en"),
    ("French", "fr"),
    ("Spanish", "es"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Dutch", "nl"),
    ("Polish", "pl"),
    ("Turkish", "tr"),
    ("Swedish", "sv"),
    ("Danish", "da"),
    ("Norwegian", "no"),
    ("Finnish", "fi"),
    ("Japanese", "ja"),
    ("Chinese", "zh"),
    ("Korean", "ko"),
]


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


def _read_key() -> str:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char = sys.stdin.read(1)
        if char == "\x1b":
            sequence = ""
            while select.select([sys.stdin], [], [], 0.03)[0]:
                sequence += sys.stdin.read(1)
            if sequence in {"[A", "OA"}:
                return UP
            if sequence in {"[B", "OB"}:
                return DOWN
            return ESCAPE
        if char in {"\r", "\n"}:
            return ENTER
        if char in {"\x7f", "\b"}:
            return BACK
        if char.lower() == "k":
            return UP
        if char.lower() == "j":
            return DOWN
        return char
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _clear_screen() -> None:
    print("\033[2J\033[H", end="")


def _select(
    title: str,
    options: list[str],
    *,
    initial: int = 0,
    allow_back: bool = True,
    escape_label: str = "Back",
) -> int | None:
    if not sys.stdin.isatty():
        for index, option in enumerate(options, start=1):
            print(f"{index}. {option}")
        raw = _prompt("Choose:")
        if not raw:
            return None
        try:
            selected = int(raw) - 1
        except ValueError:
            return None
        return selected if 0 <= selected < len(options) else None

    selected = max(0, min(initial, len(options) - 1))
    while True:
        _clear_screen()
        _banner()
        print(_rule(title))
        for index, option in enumerate(options):
            marker = ">" if index == selected else " "
            line = f" {marker} {option}"
            if index == selected:
                print(_color(line, Style.bold + Style.cyan))
            else:
                print(line)
        print()
        print(_color("Up/Down: move  Enter: select  Backspace: back  Esc: " + escape_label, Style.dim))

        key = _read_key()
        if key == UP:
            selected = (selected - 1) % len(options)
        elif key == DOWN:
            selected = (selected + 1) % len(options)
        elif key == ENTER:
            return selected
        elif key == BACK and allow_back:
            return None
        elif key == ESCAPE:
            return None
        elif key.isdigit():
            numeric = int(key) - 1
            if 0 <= numeric < len(options):
                return numeric


def _print_progress(message: str) -> None:
    prefix = _color(">", Style.cyan)
    if message.startswith("ERROR"):
        prefix = _color("!", Style.red)
        message = _color(message, Style.red)
    elif "written" in message.lower() or "ready" in message.lower() or "downloaded" in message.lower():
        prefix = _color("+", Style.green)
    print(f"  {prefix} {message}", flush=True)


def _yes_no(prompt: str, default: bool = True) -> bool:
    initial = 0 if default else 1
    selected = _select(prompt, ["Yes", "No"], initial=initial)
    return default if selected is None else selected == 0


def _choose_model(current_model: str) -> str | None:
    options = MODEL_OPTIONS.copy()
    if current_model not in options:
        options.insert(0, current_model)
    initial = options.index(current_model) if current_model in options else 0
    selected = _select("Whisper Model", options, initial=initial)
    return None if selected is None else options[selected]


def _choose_language(current_language: str | None) -> str | None | object:
    labels = [
        f"{name} ({code})" if code else name
        for name, code in LANGUAGE_OPTIONS
    ]
    codes = [code for _, code in LANGUAGE_OPTIONS]
    initial = codes.index(current_language) if current_language in codes else 0
    selected = _select("Transcription Language", labels, initial=initial)
    if selected is None:
        return BACK
    return codes[selected]


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
    _clear_screen()
    _banner()
    print("\n" + _rule(label))
    raw_input = _prompt(f"{label}:")
    if not raw_input:
        print(_color("No input provided.", Style.yellow))
        return

    transcribe = _yes_no("Run transcription after download", default=True)
    model_name = get_model_name()
    language = get_whisper_language()
    if transcribe:
        selected_model = _choose_model(model_name)
        if selected_model is None:
            return
        model_name = selected_model

        selected_language = _choose_language(language)
        if selected_language == BACK:
            return
        language = selected_language

    _clear_screen()
    _banner()
    print(_rule("Processing"))
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

    options = ["All audio files"] + [path.name for path in candidates]
    selected_index = _select("Audio Files", options)
    if selected_index is None:
        return
    if selected_index == 0:
        selected = candidates
    else:
        selected = [candidates[selected_index - 1]]
    if not selected:
        print(_color("No files selected.", Style.yellow))
        return

    _clear_screen()
    _banner()
    print(_rule("Transcription"))
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
            choice = _select(
                "Main Menu",
                [
                    "Process YouTube URL",
                    "Process RSS feed URL",
                    "Transcribe existing audio from output",
                    "View output files",
                    "Quit",
                ],
                allow_back=False,
                escape_label="Quit",
            )
            if choice is None or choice == 4:
                print(_color("Done.", Style.green))
                return 0
            if choice == 0:
                _process_source("youtube")
            elif choice == 1:
                _process_source("rss")
            elif choice == 2:
                _transcribe_existing()
            elif choice == 3:
                _show_outputs()
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

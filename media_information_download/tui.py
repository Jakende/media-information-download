from __future__ import annotations

import argparse
import os
import select
import shutil
import subprocess
import sys
import termios
import threading
import time
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
BRACKETED_PASTE_START = "[200~"
BRACKETED_PASTE_END = b"\x1b[201~"

VIEWPORT_MIN_WIDTH = 56
VIEWPORT_MAX_WIDTH = 118
VIEWPORT_MIN_HEIGHT = 14
VIEWPORT_MAX_HEIGHT = 30
VIEWPORT_LEFT_MARGIN = 2
VIEWPORT_TOP_MARGIN = 2

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


def _terminal_height() -> int:
    return max(16, shutil.get_terminal_size((88, 24)).lines)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _viewport_geometry(size: os.terminal_size | None = None) -> tuple[int, int, int, int]:
    terminal = size or shutil.get_terminal_size((100, 30))
    available_width = max(20, terminal.columns - VIEWPORT_LEFT_MARGIN)
    available_height = max(10, terminal.lines - VIEWPORT_TOP_MARGIN)
    width = _clamp(available_width, min(VIEWPORT_MIN_WIDTH, available_width), VIEWPORT_MAX_WIDTH)
    height = _clamp(available_height, min(VIEWPORT_MIN_HEIGHT, available_height), VIEWPORT_MAX_HEIGHT)
    left = max(1, min(VIEWPORT_LEFT_MARGIN, terminal.columns - width + 1))
    top = max(1, min(VIEWPORT_TOP_MARGIN, terminal.lines - height + 1))
    return top, left, width, height


def _move(row: int, column: int) -> str:
    return f"\033[{row};{column}H"


def _visible_slice(value: str, width: int) -> str:
    return value[: max(0, width)]


def _draw_viewport(title: str) -> tuple[int, int, int, int]:
    top, left, width, height = _viewport_geometry()
    inner_width = width - 2
    bottom = top + height - 1
    right = left + width - 1
    title_text = f" {title} "
    if len(title_text) > inner_width:
        title_text = title_text[:inner_width]

    top_rule = "-" * inner_width
    title_start = max(0, (inner_width - len(title_text)) // 2)
    top_rule = top_rule[:title_start] + title_text + top_rule[title_start + len(title_text):]

    print(_move(top, left) + _color("+" + top_rule + "+", Style.cyan), end="")
    for row in range(top + 1, bottom):
        print(_move(row, left) + _color("|", Style.cyan), end="")
        print(" " * inner_width, end="")
        print(_color("|", Style.cyan), end="")
    print(_move(bottom, left) + _color("+" + "-" * inner_width + "+", Style.cyan), end="")
    print(_move(top + 2, left + 2), end="", flush=True)
    return top, left, width, height


def _viewport_line(row_offset: int, text: str = "", style: str | None = None) -> None:
    top, left, width, _ = _viewport_geometry()
    inner_width = width - 4
    text = _visible_slice(text, inner_width).ljust(inner_width)
    if style:
        text = _color(text, style)
    print(_move(top + 2 + row_offset, left + 2) + text, end="")


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


def _navigation_hint(
    extra: str | None = None,
    escape_label: str = "Back",
    include_arrows: bool = True,
) -> str:
    parts = []
    if extra:
        parts.append(extra)
    if include_arrows:
        parts.append("Up/Down: move")
        parts.append("Enter: select")
    else:
        parts.append("Enter: continue")
    parts.append("Backspace: back")
    parts.append(f"Esc: {escape_label}")
    return "  ".join(parts)


def _footer(message: str) -> None:
    if sys.stdout.isatty():
        top, left, width, height = _viewport_geometry()
        row = top + height - 2
        column = left + 2
        max_width = width - 4
    else:
        row = _terminal_height()
        column = 1
        max_width = shutil.get_terminal_size((88, 24)).columns - 1

    plain_message = message[: max(1, max_width)].ljust(max_width)
    clear = "" if sys.stdout.isatty() else "\033[2K"
    print(f"\033[{row};{column}H{clear}{_color(plain_message, Style.dim)}", end="", flush=True)


def _read_bracketed_paste(fd: int) -> str:
    data = b""
    while True:
        chunk = os.read(fd, 1024)
        if not chunk:
            break
        data += chunk
        end_index = data.find(BRACKETED_PASTE_END)
        if end_index >= 0:
            data = data[:end_index]
            break
    return data.decode(errors="ignore")


def _drain_available_text(fd: int) -> str:
    data = b""
    while select.select([sys.stdin], [], [], 0.01)[0]:
        chunk = os.read(fd, 4096)
        if not chunk:
            break
        data += chunk
    return data.decode(errors="ignore")


def _read_clipboard() -> str:
    if sys.platform != "darwin":
        return ""
    result = subprocess.run(
        ["pbpaste"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def _sanitize_text_entry(value: str) -> str:
    value = value.replace("\x1b[200~", "").replace("\x1b[201~", "")
    return "".join(
        char
        for char in value
        if char.isprintable() and char not in {"\x1b", "\x7f", "\b"}
    )


def _read_key(*, text_mode: bool = False) -> str:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char = os.read(fd, 1).decode(errors="ignore")
        if char == "\x1b":
            time.sleep(0.06)
            if not select.select([sys.stdin], [], [], 0.35)[0]:
                return ESCAPE

            introducer = os.read(fd, 1).decode(errors="ignore")
            if introducer not in {"[", "O"}:
                return ESCAPE

            final = ""
            while select.select([sys.stdin], [], [], 0.10)[0]:
                final += os.read(fd, 1).decode(errors="ignore")
                if final[-1].isalpha() or final[-1] == "~":
                    break

            sequence = introducer + final
            if text_mode and sequence == BRACKETED_PASTE_START:
                return _read_bracketed_paste(fd)
            return _key_from_escape_sequence(sequence)
        if char in {"\r", "\n"}:
            return ENTER
        if char in {"\x7f", "\b"}:
            return BACK
        if text_mode and char == "\x16":
            return _read_clipboard()
        if not text_mode and char.lower() == "k":
            return UP
        if not text_mode and char.lower() == "j":
            return DOWN
        if text_mode and char.isprintable():
            return char + _drain_available_text(fd)
        return char
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _key_from_escape_sequence(sequence: str) -> str:
    if sequence in {"[A", "OA", "[1A", "[1;2A", "[1;3A", "[1;5A"}:
        return UP
    if sequence in {"[B", "OB", "[1B", "[1;2B", "[1;3B", "[1;5B"}:
        return DOWN
    return ESCAPE


def _clear_screen() -> None:
    print("\033[2J\033[H", end="")


def _clear_framed_screen(title: str) -> None:
    _clear_screen()
    _draw_viewport(title)


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
        _clear_framed_screen(title)
        row = 0
        for index, option in enumerate(options):
            marker = ">" if index == selected else " "
            line = f" {marker} {option}"
            if index == selected:
                _viewport_line(row, line, Style.bold + Style.cyan)
            else:
                _viewport_line(row, line)
            row += 1
        _footer(_navigation_hint(escape_label=escape_label))

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


def _text_entry(title: str, label: str) -> str | None:
    if not sys.stdin.isatty():
        value = _prompt(label)
        return value or None

    value = ""
    print("\033[?2004h", end="", flush=True)
    try:
        while True:
            _clear_framed_screen(title)
            _viewport_line(0, label, Style.bold + Style.blue)
            _viewport_line(2, value)
            _footer(
                _navigation_hint(
                    "Type or paste text",
                    escape_label="Back",
                    include_arrows=False,
                )
            )

            key = _read_key(text_mode=True)
            if key == ENTER:
                return value.strip() or None
            if key in {BACK, ESCAPE}:
                return None
            if key in {UP, DOWN}:
                continue
            if key == "\x15":
                value = ""
                continue
            if key == "\x03":
                raise KeyboardInterrupt
            if key:
                value += _sanitize_text_entry(key)
    finally:
        print("\033[?2004l", end="", flush=True)


def _print_progress(message: str) -> None:
    prefix = _color(">", Style.cyan)
    if message.startswith("ERROR"):
        prefix = _color("!", Style.red)
        message = _color(message, Style.red)
    elif "written" in message.lower() or "ready" in message.lower() or "downloaded" in message.lower():
        prefix = _color("+", Style.green)
    print(f"  {prefix} {message}", flush=True)


class SpinnerProgress:
    frames = ("|", "/", "-", "\\")
    active_prefixes = (
        "Downloading:",
        "Converting to MP3:",
        "Transcribing:",
    )
    terminal_prefixes = (
        "Downloaded:",
        "MP3 ready:",
        "Transcript written:",
        "ERROR:",
    )

    def __init__(self) -> None:
        self._enabled = sys.stdout.isatty()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._message = ""
        self._frame_index = 0

    def __call__(self, message: str) -> None:
        if not self._enabled:
            _print_progress(message)
            return

        if self._is_active_message(message):
            self._start(message)
            return

        if self._is_terminal_message(message):
            self.stop()
            _print_progress(message)
            return

        self.stop()
        _print_progress(message)

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return

        self._stop_event.set()
        thread.join(timeout=1)
        self._thread = None
        self._stop_event.clear()
        width = shutil.get_terminal_size((88, 24)).columns
        print("\r" + " " * max(1, width - 1) + "\r", end="", flush=True)

    def _start(self, message: str) -> None:
        with self._lock:
            self._message = message
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                message = self._message
            frame = self.frames[self._frame_index % len(self.frames)]
            self._frame_index += 1
            line = f"  {_color(frame, Style.cyan)} {message}"
            width = shutil.get_terminal_size((88, 24)).columns
            print("\r" + line[: max(1, width - 1)], end="", flush=True)
            self._stop_event.wait(0.12)

    @classmethod
    def _is_active_message(cls, message: str) -> bool:
        stripped = message.split("] ", maxsplit=1)[-1]
        return stripped.startswith(cls.active_prefixes)

    @classmethod
    def _is_terminal_message(cls, message: str) -> bool:
        return message.startswith(cls.terminal_prefixes)


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
    raw_input = _text_entry(label, f"{label}:")
    if not raw_input:
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

    if sys.stdout.isatty():
        _clear_framed_screen("Processing")
    else:
        _clear_screen()
        _banner()
        print(_rule("Processing"))
    progress = SpinnerProgress()
    try:
        pipeline = MediaPipeline(progress=progress)
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
    finally:
        progress.stop()
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

    if sys.stdout.isatty():
        _clear_framed_screen("Transcription")
    else:
        _clear_screen()
        _banner()
        print(_rule("Transcription"))
    progress = SpinnerProgress()
    try:
        pipeline = MediaPipeline(progress=progress)
        results = pipeline.transcribe_existing(selected, output_dir=output_dir)
    finally:
        progress.stop()
    _print_results(results)


def _show_outputs() -> None:
    output_dir = get_output_dir()
    files = list_output_files(output_dir)
    if not files:
        if sys.stdout.isatty():
            _clear_framed_screen("Output Files")
            _viewport_line(0, f"No output files in {output_dir}", Style.yellow)
            _footer("Backspace/Esc: back")
            while _read_key() not in {BACK, ESCAPE, ENTER}:
                pass
        else:
            print(_color(f"No output files in {output_dir}", Style.yellow))
        return

    if sys.stdout.isatty():
        _clear_framed_screen("Output Files")
        _viewport_line(0, str(output_dir), Style.dim)
        _, _, _, height = _viewport_geometry()
        max_files = max(1, height - 8)
        for index, path in enumerate(files[:max_files], start=2):
            _viewport_line(index, f"- {path.name}")
        remaining = len(files) - max_files
        if remaining > 0:
            _viewport_line(max_files + 3, f"... {remaining} more file(s)", Style.dim)
        _footer("Enter: continue  Backspace: back  Esc: Back")
        key = _read_key()
        while key not in {ENTER, BACK, ESCAPE}:
            key = _read_key()
        if key in {BACK, ESCAPE}:
            return
    else:
        print("\n" + _rule("Output Files"))
        print(_color(str(output_dir), Style.dim))
        for path in files:
            print(f"{_color('-', Style.cyan)} {path.name}")

    if sys.platform == "darwin" and _yes_no("Open output folder in Finder", default=False):
        subprocess.run(["open", str(output_dir)], check=False)


def run_tui() -> int:
    status = dependency_status(include_transcription=False)
    if status:
        if sys.stdout.isatty():
            _clear_framed_screen("Environment Warnings")
            for index, message in enumerate(status[:8]):
                _viewport_line(index, f"! {message}", Style.yellow)
            _footer("Use ./run.sh for the local project venv  Enter: continue")
            while _read_key() not in {ENTER, ESCAPE, BACK}:
                pass
        else:
            _banner()
            print(f"{_color('Output', Style.dim)} {get_output_dir()}")
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
    progress = SpinnerProgress()
    try:
        pipeline = MediaPipeline(progress=progress)
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
    finally:
        progress.stop()
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

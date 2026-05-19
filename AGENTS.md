# Agent Notes

## Project

`media-information-download` is a local terminal application for:

- collecting media items from input sources such as YouTube URLs and RSS feeds
- downloading supported media
- converting generated audio output to MP3
- transcribing MP3 files with local Whisper dependencies
- writing Markdown transcripts next to generated media

The repository is intended to run locally on macOS from its project-local virtual environment.

## Environment

- Keep dependencies local to this folder.
- Use `.venv/` for runtime dependencies.
- Do not rely on globally installed Python packages.
- `ffmpeg` may be provided by Homebrew and must remain available on `PATH`.
- Prefer running commands through `./run.sh` or the installed zsh wrapper.

Common setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-transcribe.txt
```

## Architecture

- `media_information_download/sources/`: input source adapters
- `media_information_download/downloaders/`: download implementations
- `media_information_download/audio.py`: MP3 conversion
- `media_information_download/transcription.py`: Whisper loading and transcription
- `media_information_download/output.py`: output and Markdown transcript writing
- `media_information_download/pipeline.py`: orchestration
- `media_information_download/tui.py`: terminal UI and CLI entry point
- `tests/`: focused unit tests

Keep new source types isolated behind a source adapter and downloader. Avoid adding source-specific branching throughout the pipeline.

## Output Policy

Generated media and transcripts belong in `output/` or `MEDIA_OUTPUT_DIR`. Do not commit generated media, transcripts, virtual environments, Obsidian metadata, Smart Environment metadata, or bytecode caches.

New audio output should be MP3. If a non-MP3 RSS enclosure must be downloaded as an intermediate file, convert it to MP3 and remove the intermediate file.

## Compatibility

Keep these entry points working:

- `./run.sh`
- `python3 media_tui.py`
- `python3 youtube_download.py --url ...`
- `python3 youtube_download_transcribe.py --url ...`
- `media-information-download` when installed or linked into zsh `PATH`

The interactive TUI should render inside a left-aligned framed viewport within the current terminal window. The viewport should resize responsively with terminal dimensions while staying within sensible min/max bounds. Keep selectable options navigable with Up/Down and Enter. Navigation controls should always be shown as a footer at the bottom of the active menu or submenu. Backspace should go back from submenus or choice screens. Escape should cancel/back from submenus and quit from the main menu. Free-form URL input may remain text entry, but its screen must still show controls and support Backspace/Escape as back actions.

URL entry must support paste reliably. Keep bracketed paste enabled during text-entry screens and avoid mapping text-entry characters such as `j` or `k` to navigation.

Long-running processing stages should provide visible feedback in the terminal. Keep the spinner active for download, MP3 conversion, and transcription stages, and stop it before printing completed/error status lines.

## Verification

Before handing off substantial changes, run:

```bash
source .venv/bin/activate
python -m unittest discover -s tests
python media_tui.py --help
```

For download behavior, prefer a tiny local RSS fixture or a short public YouTube video. Keep transcription checks small by using `WHISPER_MODEL=tiny`.

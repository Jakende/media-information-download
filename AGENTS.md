# Agent Notes

## Project

`media-information-download` is a local terminal application for:

- collecting media items from input sources such as YouTube URLs and RSS feeds
- downloading supported media
- converting generated audio output to MP3
- transcribing MP3 files with local Whisper dependencies
- writing Markdown transcripts next to generated media

The repository is intended to run locally from a project-local virtual environment and is also published as an npm CLI wrapper for macOS, Linux, and Windows.

## Environment

- Keep local development dependencies inside this folder.
- Use `.venv/` for direct local development/runtime dependencies.
- The npm wrapper uses `~/.media-information-download/venv` by default and sets `MEDIA_INFORMATION_DOWNLOAD_VENV` for the Python process.
- Do not rely on globally installed Python packages.
- `ffmpeg` must remain available on `PATH`. On macOS use Homebrew; on Windows use `winget install Gyan.FFmpeg`.
- Prefer running local macOS/Linux commands through `./run.sh` or the installed console script.
- On Windows, prefer `.\run.ps1`, `python media_tui.py`, or the npm-installed `media-info-cli`.

Common setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-transcribe.txt
```

Npm install:

```bash
npm install -g @jakende/media-info-cli
media-info-cli
```

Npm installs create the Python venv at `~/.media-information-download/venv` and write generated media/transcripts to `~/.media-information-download/output` unless `MEDIA_OUTPUT_DIR` is set.

Desktop output alias:

```bash
media-info-cli --desktop-output-alias
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

Generated media and transcripts belong in `output/`, `MEDIA_OUTPUT_DIR`, or the npm default `~/.media-information-download/output`. Do not commit generated media, transcripts, virtual environments, npm pack tarballs, Obsidian metadata, Smart Environment metadata, or bytecode caches.

New audio output should be MP3. If a non-MP3 RSS enclosure must be downloaded as an intermediate file, convert it to MP3 and remove the intermediate file.

## Compatibility

Keep these entry points working:

- `./run.sh`
- `python3 media_tui.py`
- `python3 youtube_download.py --url ...`
- `python3 youtube_download_transcribe.py --url ...`
- `media-information-download` when installed or linked into zsh `PATH`
- `media-info-download` when installed as a Python or npm console command
- `media-info-cli` when installed as a Python or npm console command
- `.\run.ps1` on Windows
- `npm install -g @jakende/media-info-cli` followed by `media-info-cli`

The interactive TUI should render inside a left-aligned framed viewport within the current terminal window. The viewport should resize responsively with terminal dimensions while staying within sensible min/max bounds. Keep selectable options navigable with Up/Down and Enter. Navigation controls should always be shown as a footer at the bottom of the active menu or submenu. Backspace should go back from submenus or choice screens. Escape should cancel/back from submenus and quit from the main menu. Free-form URL input may remain text entry, but its screen must still show controls and support Backspace/Escape as back actions.

URL entry must support paste reliably. Keep bracketed paste enabled during text-entry screens and avoid mapping text-entry characters such as `j` or `k` to navigation. Pasted YouTube URL lists may be separated by commas, whitespace, tabs, or line breaks.

Long-running processing stages should provide visible feedback in the terminal. Keep the framed animated activity status active for download, MP3 conversion, and transcription stages, and stop it before printing completed/error status lines. Current active labels are intentionally a little playful but functional: `TUNING IN`, `MIXING AUDIO`, and `WRITING WORDS`. Suppress third-party progress output that would write outside the viewport.

## Packaging and Release

- The npm package name is `@jakende/media-info-cli`.
- Public executable aliases are `media-info-cli`, `media-information-download`, and `media-info-download`.
- Keep `package.json` and `pyproject.toml` versions in sync before npm releases.
- The npm wrapper lives at `bin/media-information-download.js`.
- The package is MIT licensed; keep `LICENSE`, `package.json`, and `pyproject.toml` license metadata aligned.
- Publish npm releases through `.github/workflows/npm-publish.yml` using the GitHub Actions `NPM_TOKEN` secret.
- Do not publish GitHub Packages for this project unless explicitly requested; the intended public registry is `https://registry.npmjs.org/`.
- Bump the package version for every npm release because npm versions are immutable.

## Verification

Before handing off substantial changes, run:

```bash
source .venv/bin/activate
python -m unittest discover -s tests
python media_tui.py --help
npm pack --dry-run
```

For download behavior, prefer a tiny local RSS fixture or a short public YouTube video. Keep transcription checks small by using `WHISPER_MODEL=tiny`.

# Media Information Download

Terminal application for downloading media from YouTube URLs or RSS feeds, converting audio to MP3, and generating Whisper Markdown transcripts.

## Requirements

- Python 3.10+
- ffmpeg on PATH
- A terminal with ANSI escape support for the framed TUI. macOS Terminal, iTerm2, Windows Terminal, and current PowerShell terminals are supported.

Python dependencies are installed into the project-local `.venv` folder. Run commands from this folder so the local environment is used.

## macOS Setup

Option 1, installer script:

```bash
zsh scripts/install_macos.sh
./run.sh
```

Option 2, manual setup:

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-transcribe.txt
```

Optional editable install:

```bash
source .venv/bin/activate
pip install -e ".[transcribe]"
```

## Windows Setup

Use Windows Terminal or PowerShell. Install Python 3.10+ and ffmpeg first, then use the local project environment.

Option 1, installer script:

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
.\run.ps1
```

Option 2, manual setup:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-transcribe.txt
.\.venv\Scripts\python.exe -m pip install -e ".[transcribe]"
.\.venv\Scripts\python.exe media_tui.py
```

After editable install, these console commands are available inside the active environment on both platforms:

```bash
media-information-download
media-info-download
```

## npm Install

The package is also published as an npm CLI wrapper. It still requires Python 3.10+ and ffmpeg on `PATH`.

```bash
npm install -g @jakende/media-info-cli
media-information-download
```

On first run, the npm wrapper creates a Python virtual environment in `~/.media-information-download/venv` and installs the Python dependencies there. To use a different venv location:

```bash
MEDIA_INFORMATION_DOWNLOAD_VENV=/path/to/venv media-information-download
```

## TUI

```bash
./run.sh
```

or:

```bash
source .venv/bin/activate
python3 media_tui.py
```

On Windows:

```powershell
.\run.ps1
```

If the project is installed into the active environment, you can also run:

```bash
media-information-download
```

The TUI lets you choose YouTube or RSS input, start downloads, watch progress messages, trigger transcription, and list or open generated files.
Long-running download, MP3 conversion, and transcription steps show a visible `WORKING` activity bar while active.
Interactive screens render inside a left-aligned framed viewport that resizes with the current terminal window.

Keyboard controls:

- Navigation controls are shown at the bottom of the active menu or submenu
- Up/Down: move through selectable menu items
- Enter: select
- Backspace: go back from a submenu or choice screen
- Escape: cancel/back from submenus; quit from the main menu
- URL entry screens show their own controls: type or paste text, Enter continues, Backspace/Escape goes back
- Paste is supported in URL entry screens, including terminal bracketed paste, macOS clipboard paste, and Windows clipboard paste with Ctrl+V in PowerShell/Windows Terminal

For multiple YouTube URLs, separate entries with commas, spaces, or line breaks:

```text
https://youtu.be/VIDEO_ONE
https://www.youtube.com/watch?v=VIDEO_TWO, https://youtu.be/VIDEO_THREE
```

## Non-Interactive Usage

Download and transcribe a YouTube URL:

```bash
python3 media_tui.py --source youtube --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

Download and convert a YouTube URL to MP3 without transcription:

```bash
python3 media_tui.py --source youtube --url "https://www.youtube.com/watch?v=VIDEO_ID" --no-transcribe
```

Download supported media from an RSS feed and transcribe it:

```bash
python3 media_tui.py --source rss --url "https://example.com/feed.xml"
```

Compatibility commands still work:

```bash
python3 youtube_download.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
python3 youtube_download_transcribe.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Configuration

- `MEDIA_OUTPUT_DIR`: output folder. Defaults to `./output`
- `YTDL_OUTPUT_DIR`: legacy output folder fallback
- `WHISPER_MODEL`: Whisper model. Defaults to `large`
- `WHISPER_LANGUAGE`: optional language code. If unset, Whisper auto-detects language
- `YTDL_COOKIES_FROM_BROWSER`: optional browser cookies for YouTube, for example `safari` or `chrome`

All generated audio is saved as `.mp3`. Non-MP3 RSS downloads are converted and removed as intermediates, so new RSS audio output does not remain as `.wav`. Transcripts are saved as `.md` next to the MP3 files.

## Architecture

- `media_tui.py`: direct script entry point
- `youtube_download.py`: compatibility entry point for YouTube download and MP3 conversion
- `youtube_download_transcribe.py`: compatibility entry point for YouTube download, MP3 conversion, and transcription
- `media_information_download/sources/`: input source handling for YouTube and RSS
- `media_information_download/downloaders/`: YouTube and HTTP media downloaders
- `media_information_download/audio.py`: audio extraction and MP3 conversion
- `media_information_download/transcription.py`: Whisper model loading and transcription, adapted from the macOS transcription workflow
- `media_information_download/output.py`: Markdown transcript and output file handling
- `media_information_download/pipeline.py`: orchestration across source, download, conversion, transcription, and output
- `media_information_download/tui.py`: terminal UI and non-interactive CLI entry point

This structure keeps new media sources or formats isolated to source handlers, downloaders, and supported format lists.

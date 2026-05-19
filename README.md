# Media Information Download

Terminal application for downloading media from YouTube URLs or RSS feeds, converting audio to MP3, and generating Whisper Markdown transcripts.

## Requirements

- Python 3.10+
- ffmpeg on PATH, for example `brew install ffmpeg`

Python dependencies are installed into the project-local `.venv` folder. Run commands from this folder so the local environment is used.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-transcribe.txt
```

Optional editable install:

```bash
source .venv/bin/activate
pip install -e ".[transcribe]"
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

If the project wrapper is linked into your zsh `PATH`, you can also run:

```bash
media-information-download
```

The TUI lets you choose YouTube or RSS input, start downloads, watch progress messages, trigger transcription, and list or open generated files.

Keyboard controls:

- Up/Down: move through selectable menu items
- Enter: select
- Backspace: go back from a submenu or choice screen
- Escape: cancel/back from submenus; quit from the main menu

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

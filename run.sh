#!/usr/bin/env zsh
set -euo pipefail

project_dir="${0:A:h}"
cd "$project_dir"

if [[ ! -x ".venv/bin/python" ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import yt_dlp, whisper, torch" >/dev/null 2>&1; then
  pip install -r requirements-transcribe.txt
fi

exec python media_tui.py "$@"

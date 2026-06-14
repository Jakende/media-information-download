#!/usr/bin/env zsh
set -euo pipefail

project_dir="${0:A:h:h}"
cd "$project_dir"

if ! command -v python3 >/dev/null 2>&1; then
  print -u2 "python3 is required. Install Python 3.10+ first."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  print -u2 "ffmpeg is not available on PATH."
  print -u2 "Install it with Homebrew: brew install ffmpeg"
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-transcribe.txt
python -m pip install -e ".[transcribe]"

print "Installed local environment."
print "Run: ./run.sh"
print "Or:  media-information-download"

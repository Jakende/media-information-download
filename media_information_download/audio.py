from __future__ import annotations

import subprocess
from pathlib import Path


def convert_to_mp3(media_path: Path, output_dir: Path) -> Path:
    mp3_path = output_dir / f"{media_path.stem}.mp3"
    if media_path.resolve() == mp3_path.resolve() and mp3_path.exists():
        return mp3_path

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(mp3_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error_tail = (result.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError("ffmpeg failed to create MP3. " + " ".join(error_tail))
    return mp3_path

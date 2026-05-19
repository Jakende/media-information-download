from __future__ import annotations

from datetime import datetime
from pathlib import Path

from media_information_download.models import MediaItem
from media_information_download.transcription import seconds_to_timecode


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_markdown(
    item: MediaItem,
    audio_path: Path,
    model_name: str,
    device: str,
    language: str,
    fps: int,
    segments: list[dict],
    full_text: str,
    include_timecodes: bool = True,
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    segment_blocks = []
    for seg in segments:
        start_tc = seconds_to_timecode(float(seg.get("start", 0.0)), fps=fps)
        end_tc = seconds_to_timecode(float(seg.get("end", 0.0)), fps=fps)
        seg_text = (seg.get("text") or "").strip()
        if seg_text:
            segment_blocks.append(f"{start_tc} - {end_tc}\n{seg_text}")

    transcript_body = "\n\n".join(segment_blocks).strip() if include_timecodes and segment_blocks else full_text
    return f"""\
---
created: {yaml_quote(timestamp)}
model: {yaml_quote(model_name)}
device: {yaml_quote(device)}
language: {yaml_quote(language)}
source_type: {yaml_quote(item.source_type)}
source_url: {yaml_quote(item.source_url)}
media_url: {yaml_quote(item.media_url)}
source_file: {yaml_quote(audio_path.name)}
fps_timecode: {fps}
timecodes: {str(include_timecodes).lower()}
---

# Transkript: {item.title}

---

{transcript_body}
"""


def write_transcript(
    output_dir: Path,
    item: MediaItem,
    audio_path: Path,
    model_name: str,
    device: str,
    language: str,
    fps: int,
    segments: list[dict],
    full_text: str,
) -> Path:
    md_path = output_dir / f"{audio_path.stem}.md"
    markdown = build_markdown(
        item=item,
        audio_path=audio_path,
        model_name=model_name,
        device=device,
        language=language,
        fps=fps,
        segments=segments,
        full_text=full_text,
    )
    md_path.write_text(markdown, encoding="utf-8")
    return md_path


def list_output_files(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted(path for path in output_dir.iterdir() if path.is_file())

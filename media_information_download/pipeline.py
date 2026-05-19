from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from media_information_download.audio import convert_to_mp3
from media_information_download.config import (
    get_model_name,
    get_output_dir,
    get_whisper_language,
    require_dependencies,
)
from media_information_download.downloaders.http import HTTPDownloader
from media_information_download.downloaders.youtube import YouTubeDownloader
from media_information_download.models import MediaItem, ProcessedMedia, ProgressCallback
from media_information_download.output import write_transcript
from media_information_download.sources.rss import RSSSource
from media_information_download.sources.youtube import YouTubeSource
from media_information_download.transcription import WhisperTranscriber


@dataclass(frozen=True)
class ProcessOptions:
    source_type: str
    raw_input: str
    output_dir: Path | None = None
    transcribe: bool = True
    model_name: str | None = None
    language: str | None = None
    fps: int = 25
    delay_seconds: float = 2.0


class MediaPipeline:
    def __init__(self, progress: ProgressCallback | None = None) -> None:
        self.progress = progress or (lambda message: None)

    def _source(self, source_type: str):
        if source_type == "youtube":
            return YouTubeSource()
        if source_type == "rss":
            return RSSSource()
        raise ValueError(f"Unsupported source type: {source_type}")

    def _downloader(self, item: MediaItem):
        if item.source_type == "youtube":
            return YouTubeDownloader()
        if item.source_type == "rss":
            return HTTPDownloader()
        raise ValueError(f"Unsupported source type: {item.source_type}")

    def collect_items(self, options: ProcessOptions) -> list[MediaItem]:
        return self._source(options.source_type).collect(options.raw_input)

    def process(self, options: ProcessOptions) -> list[ProcessedMedia]:
        require_dependencies(include_transcription=options.transcribe)
        output_dir = (options.output_dir or get_output_dir()).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        self.progress(f"Collecting media from {options.source_type} input...")
        items = self.collect_items(options)
        self.progress(f"Found {len(items)} media item(s).")

        transcriber: WhisperTranscriber | None = None
        if options.transcribe:
            model_name = options.model_name or get_model_name()
            transcriber = WhisperTranscriber(
                model_name=model_name,
                language=options.language if options.language is not None else get_whisper_language(),
            )

        results: list[ProcessedMedia] = []
        for index, item in enumerate(items, start=1):
            result = ProcessedMedia(item=item)
            results.append(result)
            self.progress(f"[{index}/{len(items)}] Downloading: {item.title}")
            try:
                downloaded_path = self._downloader(item).download(item, output_dir)
                result.downloaded_path = downloaded_path
                self.progress(f"Downloaded: {downloaded_path.name}")

                mp3_path = convert_to_mp3(downloaded_path, output_dir)
                result.mp3_path = mp3_path
                self.progress(f"MP3 ready: {mp3_path.name}")

                if item.source_type == "rss" and downloaded_path.resolve() != mp3_path.resolve():
                    downloaded_path.unlink(missing_ok=True)
                    result.notes.append(f"Removed intermediate media file: {downloaded_path.name}")
                    result.downloaded_path = None

                if transcriber is not None:
                    self.progress(f"Transcribing: {mp3_path.name}")
                    transcript, language, device = transcriber.transcribe(mp3_path)
                    result.transcript_path = write_transcript(
                        output_dir=output_dir,
                        item=item,
                        audio_path=mp3_path,
                        model_name=transcriber.model_name,
                        device=device,
                        language=language,
                        fps=options.fps,
                        segments=transcript.get("segments", []),
                        full_text=(transcript.get("text") or "").strip(),
                    )
                    self.progress(f"Transcript written: {result.transcript_path.name}")
            except Exception as exc:
                result.error = str(exc)
                self.progress(f"ERROR: {exc}")
                if "HTTP Error 403" in str(exc):
                    result.notes.append(
                        "YouTube rejected the media request. Try setting "
                        'YTDL_COOKIES_FROM_BROWSER="safari" or "chrome".'
                    )

            if index < len(items) and options.delay_seconds > 0:
                time.sleep(max(0.0, options.delay_seconds))

        return results

    def transcribe_existing(
        self,
        audio_paths: list[Path],
        output_dir: Path | None = None,
        model_name: str | None = None,
        language: str | None = None,
        fps: int = 25,
    ) -> list[ProcessedMedia]:
        require_dependencies(include_transcription=True)
        target_output_dir = (output_dir or get_output_dir()).resolve()
        transcriber = WhisperTranscriber(
            model_name=model_name or get_model_name(),
            language=language if language is not None else get_whisper_language(),
        )
        results: list[ProcessedMedia] = []
        for index, audio_path in enumerate(audio_paths, start=1):
            item = MediaItem(
                source_type="local",
                source_url=str(audio_path),
                media_url=str(audio_path),
                title=audio_path.stem,
            )
            result = ProcessedMedia(item=item, mp3_path=audio_path)
            results.append(result)
            try:
                self.progress(f"[{index}/{len(audio_paths)}] Transcribing: {audio_path.name}")
                transcript, detected_language, device = transcriber.transcribe(audio_path)
                result.transcript_path = write_transcript(
                    output_dir=target_output_dir,
                    item=item,
                    audio_path=audio_path,
                    model_name=transcriber.model_name,
                    device=device,
                    language=detected_language,
                    fps=fps,
                    segments=transcript.get("segments", []),
                    full_text=(transcript.get("text") or "").strip(),
                )
                self.progress(f"Transcript written: {result.transcript_path.name}")
            except Exception as exc:
                result.error = str(exc)
                self.progress(f"ERROR: {exc}")
        return results

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import wave
import os
from pathlib import Path
from unittest import mock

from media_information_download.audio import convert_to_mp3
from media_information_download.config import is_project_venv_active
from media_information_download.sources.rss import parse_feed_xml
from media_information_download.sources.youtube import parse_urls, validate_url
from media_information_download.tui import (
    DOWN,
    ESCAPE,
    UP,
    SpinnerProgress,
    _key_from_escape_sequence,
    _sanitize_text_entry,
    _viewport_geometry,
)


class MediaPipelineTests(unittest.TestCase):
    def test_youtube_url_validation_accepts_standard_urls(self) -> None:
        self.assertTrue(validate_url("https://www.youtube.com/watch?v=abcdefghijk"))
        self.assertTrue(validate_url("https://youtu.be/abcdefghijk"))
        self.assertFalse(validate_url("https://example.com/video"))

    def test_youtube_url_parser_accepts_pasted_lists(self) -> None:
        self.assertEqual(
            parse_urls(
                "https://youtu.be/abcdefghijk,\n"
                "https://www.youtube.com/watch?v=lmnopqrstuv "
                "https://youtu.be/wxyzabcdefg"
            ),
            [
                "https://youtu.be/abcdefghijk",
                "https://www.youtube.com/watch?v=lmnopqrstuv",
                "https://youtu.be/wxyzabcdefg",
            ],
        )

    def test_tui_arrow_escape_sequences_do_not_map_to_escape(self) -> None:
        self.assertEqual(_key_from_escape_sequence("[A"), UP)
        self.assertEqual(_key_from_escape_sequence("OA"), UP)
        self.assertEqual(_key_from_escape_sequence("[B"), DOWN)
        self.assertEqual(_key_from_escape_sequence("OB"), DOWN)
        self.assertEqual(_key_from_escape_sequence("[1;5A"), UP)
        self.assertEqual(_key_from_escape_sequence("[1;5B"), DOWN)
        self.assertEqual(_key_from_escape_sequence("[C"), ESCAPE)

    def test_spinner_progress_detects_long_running_stages(self) -> None:
        self.assertTrue(SpinnerProgress._is_active_message("[1/2] Downloading: Example"))
        self.assertTrue(SpinnerProgress._is_active_message("Converting to MP3: Example.mp4"))
        self.assertTrue(SpinnerProgress._is_active_message("Transcribing: Example.mp3"))
        self.assertTrue(SpinnerProgress._is_terminal_message("Downloaded: Example.mp4"))
        self.assertTrue(SpinnerProgress._is_terminal_message("MP3 ready: Example.mp3"))
        self.assertTrue(SpinnerProgress._is_terminal_message("Transcript written: Example.md"))
        self.assertFalse(SpinnerProgress._is_active_message("Found 1 media item(s)."))

    def test_text_entry_sanitizes_pasted_control_sequences(self) -> None:
        self.assertEqual(
            _sanitize_text_entry("https://www.youtube.com/watch?v=abc123\x1b[201~"),
            "https://www.youtube.com/watch?v=abc123",
        )
        self.assertEqual(
            _sanitize_text_entry("\x1b[200~https://youtu.be/abc\x1b[201~"),
            "https://youtu.be/abc",
        )
        self.assertEqual(
            _sanitize_text_entry("https://youtu.be/abc\r\nhttps://youtu.be/def"),
            "https://youtu.be/abc,https://youtu.be/def",
        )
        self.assertEqual(_sanitize_text_entry("https://youtu.be/abc\x7f"), "https://youtu.be/abc")

    def test_viewport_geometry_is_left_aligned_and_responsive(self) -> None:
        large = _viewport_geometry(os.terminal_size((160, 50)))
        small = _viewport_geometry(os.terminal_size((70, 20)))
        self.assertEqual(large[1], 2)
        self.assertEqual(small[1], 2)
        self.assertGreater(large[2], small[2])
        self.assertGreater(large[3], small[3])

    def test_npm_venv_environment_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            venv_path = Path(tmp).resolve()
            with mock.patch.dict(os.environ, {"MEDIA_INFORMATION_DOWNLOAD_VENV": str(venv_path)}):
                with mock.patch("media_information_download.config.sys.prefix", str(venv_path)):
                    self.assertTrue(is_project_venv_active())

    def test_rss_parser_extracts_supported_enclosure(self) -> None:
        feed = b"""<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Episode 1</title>
              <enclosure url="https://example.com/audio/episode-1.mp3" type="audio/mpeg" />
            </item>
          </channel>
        </rss>
        """
        items = parse_feed_xml(feed, "https://example.com/feed.xml")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Episode 1")
        self.assertEqual(items[0].media_url, "https://example.com/audio/episode-1.mp3")

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_convert_to_mp3_writes_mp3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wav_path = tmp_path / "sample.wav"
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(8000)
                wav_file.writeframes(b"\x00\x00" * 8000)

            mp3_path = convert_to_mp3(wav_path, tmp_path)
            self.assertEqual(mp3_path.suffix, ".mp3")
            self.assertTrue(mp3_path.exists())

            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=format_name", "-of", "default=nw=1", str(mp3_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(probe.returncode, 0)
            self.assertIn("mp3", probe.stdout)


if __name__ == "__main__":
    unittest.main()

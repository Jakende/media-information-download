from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from media_information_download.audio import convert_to_mp3
from media_information_download.sources.rss import parse_feed_xml
from media_information_download.sources.youtube import validate_url


class MediaPipelineTests(unittest.TestCase):
    def test_youtube_url_validation_accepts_standard_urls(self) -> None:
        self.assertTrue(validate_url("https://www.youtube.com/watch?v=abcdefghijk"))
        self.assertTrue(validate_url("https://youtu.be/abcdefghijk"))
        self.assertFalse(validate_url("https://example.com/video"))

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

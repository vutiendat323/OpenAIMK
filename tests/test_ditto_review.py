"""An upstream renderer must not silently pass an incomplete audiovisual clip."""

import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from scripts.review_ditto_source import validate_render


class DittoRenderValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.audio = Path(self.tmp.name) / "input.wav"
        with wave.open(str(self.audio), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(bytes(32000))

    def validate(self, streams):
        with patch(
            "scripts.review_ditto_source.subprocess.check_output",
            return_value=json.dumps({"streams": streams}).encode(),
        ):
            return validate_render(Path(self.tmp.name) / "output.mp4", self.audio)

    def test_complete_streams(self):
        result = self.validate(
            [
                {"codec_type": "video", "nb_frames": "25"},
                {"codec_type": "audio", "duration": "1.0"},
            ]
        )
        self.assertEqual(result, {"frames": 25, "audio_seconds": 1.0})

    def test_missing_audio_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Missing video/audio"):
            self.validate([{"codec_type": "video", "nb_frames": "25"}])

    def test_short_video_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Truncated video"):
            self.validate(
                [
                    {"codec_type": "video", "nb_frames": "15"},
                    {"codec_type": "audio", "duration": "1.0"},
                ]
            )

    def test_short_audio_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Truncated audio"):
            self.validate(
                [
                    {"codec_type": "video", "nb_frames": "25"},
                    {"codec_type": "audio", "duration": "0.5"},
                ]
            )

"""Port OpenJarvis's test_speaker_audio.py onto SpeakerStream.

usage: port_stream_tests.py SOURCE DEST

Only the harness changes: the Pipecat pipeline becomes a reference host that
forwards each microphone chunk (as the processor did before handling it) and
calls the stream; verdict and STT frames arrive through the two callbacks.
Every assertion stays. Each edit must match the expected number of times.
"""

from __future__ import annotations

import sys
from pathlib import Path

IMPORTS = '''"""The speaker stream turns diarizer output into verdicts and delayed STT audio.

Ported from OpenJarvis tests/server/test_speaker_audio.py. Only the harness
changed: a reference host forwards each mic chunk, as the Pipecat processor did
before handling it, and drives SpeakerStream through calls and callbacks.
"""

from __future__ import annotations

import asyncio
import logging
import time as _time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from audio.speaker import (
    AudioOnlyGate,
    FaceTrackBuffer,
    SpeakerSettings,
    Verdict,
)
from audio.speaker_identity import (
    EmbeddingJob,
    FusionGate,
    SlotIdentity,
)
from audio.speaker_stream import AudioChunk, SpeakerStream, SpeakerVerdict, SttAudio
from audio.speaker_vision import AudioSpan

'''

HARNESS = '''class BotStarted:
    """The host saw bot playback start (was BotStartedSpeakingFrame)."""


class BotStopped:
    """The host saw bot playback stop (was BotStoppedSpeakingFrame)."""


class _Collector:
    """What a host downstream of the stream receives, in order."""

    def __init__(self):
        self.audio = 0
        self.audio_bytes = []
        self.verdicts = []
        self.stt = []

    async def process_frame(self, frame, direction=None):
        if isinstance(frame, AudioChunk):
            self.audio += 1
            self.audio_bytes.append(frame.audio)
        if isinstance(frame, SpeakerVerdict):
            self.verdicts.append(frame.verdict)
        if isinstance(frame, SttAudio):
            self.stt.append(frame)


def _audio(samples=CHUNK, rate=16_000, channels=1):
    return AudioChunk(
        audio=np.zeros(samples * channels, np.int16).tobytes(),
        sample_rate=rate,
        num_channels=channels,
    )


async def _run(processor, frames, *, until=lambda: True, collector=None):
    """Drive the stream as a host would: start, forward and push, then end."""
    collector = collector or _Collector()

    async def deliver(item):
        await collector.process_frame(item, None)

    processor.on_verdict = deliver
    processor.on_stt_audio = deliver

    async def drive():
        await processor.start()
        await asyncio.sleep(0.05)
        for frame in frames:
            if isinstance(frame, BotStarted):
                processor.bot_started()
            elif isinstance(frame, BotStopped):
                processor.bot_stopped()
            else:
                # The processor pushed the live mic on before handling it.
                await collector.process_frame(frame, None)
                processor.push_audio(frame)
            await asyncio.sleep(0)
        # Wait on the outcome, not a fixed sleep: a cold start can take
        # longer than any fixed settle time.
        for _ in range(200):
            if until():
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        await processor.finish()
        await processor.close()

    await asyncio.wait_for(drive(), timeout=10)
    return collector


'''

OLD_LOG_TEST = """async def test_the_fusion_session_summary_counts_bookkeeping_errors():
    import openjarvis.server.voice.speaker_audio as speaker_audio

    processor, _ = _fusion_processor(_fusion_gate())
    processor._fusion_row_errors = 3
    messages = []
    sink = speaker_audio.logger.add(
        lambda message: messages.append(str(message)), level="INFO"
    )
    try:
        await processor._stop()
    finally:
        speaker_audio.logger.remove(sink)
    (line,) = [m for m in messages if "speaker_fusion session" in m]
    assert "fusion_row_errors=3" in line
"""

NEW_LOG_TEST = """async def test_the_fusion_session_summary_counts_bookkeeping_errors(caplog):
    processor, _ = _fusion_processor(_fusion_gate())
    processor._fusion_row_errors = 3
    with caplog.at_level(logging.INFO):
        await processor._stop()
    messages = [record.getMessage() for record in caplog.records]
    (line,) = [m for m in messages if "speaker_fusion session" in m]
    assert "fusion_row_errors=3" in line
"""

# (old, new, expected occurrences in the body)
EDITS = [
    (OLD_LOG_TEST, NEW_LOG_TEST, 1),
    ("InputAudioRawFrame(", "AudioChunk(", 4),
    ("BotStartedSpeakingFrame()", "BotStarted()", 1),
    ("BotStoppedSpeakingFrame()", "BotStopped()", 1),
    ("SpeakerAudioProcessor", "SpeakerStream", 18),
    ("SttAudioFrame", "SttAudio", 4),
    ("SpeakerVerdictFrame", "SpeakerVerdict", 3),
    (
        "async def push_frame(self, frame, direction=FrameDirection.DOWNSTREAM):",
        "async def _push_verdict(self, frame):",
        2,
    ),
    (
        "await super().push_frame(frame, direction)",
        "await super()._push_verdict(frame)",
        2,
    ),
    (
        "async def push(frame, direction=FrameDirection.DOWNSTREAM):",
        "async def push(frame):",
        3,
    ),
    ("processor.push_frame = push", "processor.on_stt_audio = push", 3),
    (
        "from openjarvis.server.voice.speaker_vision import VisionAudioBridge",
        "from audio.speaker_vision import VisionAudioBridge",
        1,
    ),
]
LEFTOVERS = ("pipecat", "FrameDirection", "openjarvis", "push_frame", "queue_frame")


def main() -> None:
    source, dest = map(Path, sys.argv[1:])
    text = source.read_text()
    # Imports: everything above the chunk size constant.
    text = IMPORTS + text[text.index("CHUNK = 320") :]
    # Harness: from the Pipecat collector to the first helper that stays.
    start = text.index("class _Collector(FrameProcessor):")
    end = text.index("def _processor(rows):")
    text = text[:start] + HARNESS + text[end:]
    for old, new, expected in EDITS:
        found = text.count(old)
        if found != expected:
            raise SystemExit(f"expected {expected} x {old[:60]!r}, found {found}")
        text = text.replace(old, new)
    left = [word for word in LEFTOVERS if word in text]
    if left:
        raise SystemExit(f"{dest}: still mentions {left}")
    dest.write_text(text)
    print(f"{source.name} -> {dest}")


if __name__ == "__main__":
    main()

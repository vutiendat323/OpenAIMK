"""Port OpenJarvis's SpeakerAudioProcessor into the framework-neutral SpeakerStream.

usage: port_stream.py SPEAKER_AUDIO_PY DEST

Copies the processor (from DIARIZER_EXECUTOR to the end of the file) under a
neutral header and replaces only its Pipecat plumbing: process_frame becomes
start / push_audio / bot_started / bot_stopped / finish / close, push_frame
becomes the two callbacks, Pipecat tasks become asyncio tasks. Each edit must
match exactly the expected number of times.
"""

from __future__ import annotations

import sys
from pathlib import Path

HEADER = '''"""Diarize the customer mic; emit speaker verdicts and a delayed STT copy.

Framework-neutral port of OpenJarvis's SpeakerAudioProcessor: a host turns its
own frames into calls (start, push_audio, bot_started, bot_stopped, drain,
finish, close) and receives SpeakerVerdict and SttAudio through two
callbacks. Only that plumbing changed; the logic below is the processor's.
"""

from __future__ import annotations

import asyncio
import bisect
import logging
import math
import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import numpy as np

from audio.speaker import SEGMENT_MAX_SECS, AudioOnlyGate, Verdict
from audio.speaker_console import LiveKey, SettingsStore, SpeakerConsole
from audio.speaker_embedding import EmbeddingWorker, SpeakerEmbedder
from audio.speaker_identity import EmbeddingJob, FusionGate
from audio.speaker_models import SAMPLE_RATE, Diarizer, Separator
from audio.speaker_vision import AudioSpan, VisionAudioBridge

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioChunk:
    """Microphone PCM16 as the host received it (was InputAudioRawFrame)."""

    audio: bytes
    sample_rate: int
    num_channels: int

    @property
    def num_frames(self) -> int:
        return int(len(self.audio) / (self.num_channels * 2))


@dataclass(frozen=True)
class SpeakerVerdict:
    """The gate's verdict for one diarizer frame (was SpeakerVerdictFrame)."""

    verdict: Verdict = Verdict.UNCERTAIN
    locked: bool = False  # a customer is locked (fusion)
    overlap_target: bool = False  # the customer talks over another voice
    source: str | None = None  # asd | mar | voice | audio


@dataclass(frozen=True)
class SttAudio:
    """Delayed mic audio for STT, rejected speech silenced (was SttAudioFrame)."""

    audio: bytes = b""
    sample_rate: int = 16_000
    num_channels: int = 1
    # The gate's verdict for this audio and why it was kept or silenced.
    verdict: str = ""
    reason: str = ""


async def _discard(_item) -> None:
    """Default callback: the host did not ask for this output."""


'''

START = "# One GPU model, one thread: pushes and resets never interleave.\n"

METHODS = '''    def __str__(self) -> str:
        return self._name

    # ConsoleSource: what the operator console reads.
    @property
    def gate(self) -> AudioOnlyGate:
        return self._gate

    @property
    def fusion(self) -> FusionGate | None:
        return self._fusion

    @property
    def bridge(self):
        return self._vision_audio

    @property
    def bot_audible_until(self) -> float:
        return self._bot_audible_until

    @property
    def tse_ready(self) -> bool:
        return (
            self._separator is not None
            and self._enrolled >= self._separator.enroll_samples
        )

    @property
    def bargein_blocked(self) -> int:
        return getattr(self._tracker, "bargein_blocked", 0)

    async def start(self) -> None:
        """The session started (was StartFrame)."""
        if self._vision_audio is not None:
            await self._vision_audio.start()
        self._executor.submit(self._diarizer.reset)
        self._worker = asyncio.create_task(self._diarize(), name="diarize")
        if self._stt_delay:
            self._releaser = asyncio.create_task(
                self._release_loop(), name="stt_release"
            )

    def bot_started(self) -> None:
        """Bot playback started (was BotStartedSpeakingFrame)."""
        self._bot_audible_until = math.inf

    def bot_stopped(self) -> None:
        """Bot playback stopped (was BotStoppedSpeakingFrame)."""
        self._bot_audible_until = time.monotonic() + BOT_TAIL_SECS

    def push_audio(self, frame: AudioChunk) -> None:
        """One microphone chunk (was a downstream audio frame).

        Never waits on the model; the host forwards its own copy to the VAD.
        """
        span = None
        if self._vision_audio is not None:
            span = self._vision_audio.offer(
                frame.audio, frame.sample_rate, frame.num_channels
            )
        if self._stt_delay:
            arrival = span.end if span is not None else time.time()
            self._stt_line.append((arrival, frame))
        self._enqueue(frame, span)
        if self._console is not None:
            try:
                self._console.audio(frame.audio)
            except Exception:
                logger.exception("operator console audio observation failed")

    async def finish(self) -> None:
        """The session is ending: send what is left, without a GPU call."""
        if self._stt_delay:
            await self._release_stt(math.inf, separate=False)

    async def close(self) -> None:
        """Report the session and stop (was EndFrame / CancelFrame)."""
        await self._stop()

    async def _push_verdict(self, verdict: SpeakerVerdict) -> None:
        await self.on_verdict(verdict)

'''

# (old, new, expected occurrences after the process_frame splice)
EDITS = [
    ("class SpeakerAudioProcessor(FrameProcessor):", "class SpeakerStream:", 1),
    ("for Gemini (``SttAudioFrame``)", "for STT (``SttAudio``)", 1),
    (
        "        target_audio_monitor: Any | None = None,\n"
        "        **kwargs,\n"
        "    ) -> None:\n"
        "        super().__init__(**kwargs)\n"
        "        self._stt_delay = stt_delay_secs\n",
        "        target_audio_monitor: Any | None = None,\n"
        "        live_keys: Sequence[LiveKey] = (),\n"
        "        settings_store: SettingsStore | None = None,\n"
        "        on_verdict: Callable[[SpeakerVerdict], Awaitable[None]] = _discard,\n"
        "        on_stt_audio: Callable[[SttAudio], Awaitable[None]] = _discard,\n"
        '        name: str = "SpeakerStream",\n'
        "    ) -> None:\n"
        "        self.on_verdict = on_verdict\n"
        "        self.on_stt_audio = on_stt_audio\n"
        "        self._name = name\n"
        "        self._stt_delay = stt_delay_secs\n",
        1,
    ),
    (
        "            from openjarvis.server.voice.speaker_console import SpeakerConsole\n"
        "\n"
        "            self._console = SpeakerConsole(\n"
        "                self, speaker_settings, audio_enhancer, target_audio_monitor,\n"
        "            )\n",
        "            self._console = SpeakerConsole(\n"
        "                self, speaker_settings, enhancer=audio_enhancer,\n"
        "                target_audio_monitor=target_audio_monitor,\n"
        "                live_keys=live_keys, store=settings_store,\n"
        "            )\n",
        1,
    ),
    ("InputAudioRawFrame", "AudioChunk", 6),
    (
        "                        await self.push_frame(\n"
        "                            SpeakerVerdictFrame(",
        "                        await self._push_verdict(\n"
        "                            SpeakerVerdict(",
        1,
    ),
    (
        "        await self.push_frame(\n            SttAudioFrame(",
        "        await self.on_stt_audio(\n            SttAudio(",
        1,
    ),
    (
        "        if self._releaser is not None:\n"
        "            await self.cancel_task(self._releaser)\n"
        "            self._releaser = None\n"
        "        if self._worker is not None:\n"
        "            await self.cancel_task(self._worker)\n"
        "            self._worker = None\n",
        "        for task in (self._releaser, self._worker):\n"
        "            if task is not None:\n"
        "                task.cancel()\n"
        "                await asyncio.gather(task, return_exceptions=True)\n"
        "        self._releaser = self._worker = None\n",
        1,
    ),
    (
        "\n    async def cleanup(self) -> None:\n"
        "        await self._stop()\n"
        "        await super().cleanup()\n",
        "",
        1,
    ),
]
LEFTOVERS = (
    "pipecat",
    "FrameProcessor",
    "push_frame",
    "cancel_task",
    "openjarvis",
    "super()",
    "Frame(",
    "FrameDirection",
)


def main() -> None:
    source, dest = map(Path, sys.argv[1:])
    text = source.read_text()
    body = text[text.index(START) :]
    start = body.index("    async def process_frame(")
    end = body.index("    def _enqueue(")
    body = body[:start] + METHODS + body[end:]
    for old, new, expected in EDITS:
        found = body.count(old)
        if found != expected:
            raise SystemExit(f"expected {expected} x {old[:60]!r}, found {found}")
        body = body.replace(old, new)
    left = [word for word in LEFTOVERS if word in body]
    if left:
        raise SystemExit(f"{dest}: still mentions {left}")
    dest.write_text(HEADER + body)
    print(f"{source.name} -> {dest}")


if __name__ == "__main__":
    main()

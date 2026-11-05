"""The roles the application depends on, met structurally by adapters and hosts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from audio.domain.evidence import AudioSpan, FaceTrackBuffer
from audio.domain.fusion import FusionGate
from audio.domain.gate import AudioOnlyGate


class AsdBridge(Protocol):
    """Vision's active-speaker client, as SpeakerStream drives it.

    Optional members are read with getattr or hasattr: audio_seconds,
    last_wait_timed_out, pin, asd_late, asd_age_ms, protocol_version,
    offer_telemetry and console.
    """

    stream_id: str | None

    async def start(self) -> None: ...

    def offer(self, audio: bytes, sample_rate: int, num_channels: int) -> AudioSpan: ...

    async def wait_for_evidence(
        self,
        faces: FaceTrackBuffer,
        t0: float,
        t1: float,
        *,
        timeout: float,
        track_id: int | None = None,
    ) -> None: ...

    async def close(self) -> None: ...


class Diarizer(Protocol):
    """Streaming speaker diarization, one fixed-size chunk at a time."""

    frame_secs: float
    chunk_samples: int

    def reset(self) -> None: ...

    def push(self, pcm: np.ndarray) -> np.ndarray:
        """int16 mono of ``chunk_samples`` -> (frames, speakers) probabilities."""
        ...


class Separator(Protocol):
    """Target-speaker extraction over a held stretch of mixed audio."""

    window_samples: int
    enroll_samples: int

    def separate(self, mix: np.ndarray, enroll: np.ndarray) -> np.ndarray:
        """float32 mix (<= ``window_samples``) + enrollment -> the target's audio."""
        ...


class SpeakerEmbedder(Protocol):
    def embed(self, pcm: np.ndarray) -> np.ndarray:
        """int16 mono 16 kHz -> one float32 speaker embedding."""
        ...


@dataclass(frozen=True)
class LiveKey:
    """A host-owned value the operator may tune, such as a kiosk distance."""

    name: str
    bounds: tuple[float, float]
    get: Callable[[], float]
    set: Callable[[float], None]


class TelemetrySink(Protocol):
    asd_late: int
    asd_age_ms: Sequence[float]

    def offer_telemetry(self, snapshot: dict) -> None: ...


class ConsoleSource(Protocol):
    """What the console reads from the host's audio pipeline."""

    gate: AudioOnlyGate
    fusion: FusionGate | None
    bridge: TelemetrySink
    bot_audible_until: float  # a time.monotonic() deadline
    tse_ready: bool
    stt_masked_no_verdict: int
    bargein_blocked: int


class SettingsStore(Protocol):
    def save(self, values: Mapping[str, float]) -> None: ...

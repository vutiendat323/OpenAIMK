"""Active-speaker domain types and the bounded audio/video window buffer.

``AsdWindow``/``AsdResult`` are the typed values that cross into the model
provider and back.  ``AVBuffer`` is the thread-safe hand-off: it accumulates
80 ms audio packets and 15 Hz face crops for the one currently selected
track, assembles the newest complete 1 s/25-crop window on demand, and holds
the latest published result.  It never touches the model.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

PACKET_SECS = 0.080
PACKET_SAMPLES = 1280
WINDOW_SECS = 1.0
WINDOW_SAMPLES = 16000
NUM_BINS = 25
BIN_STEP_SECS = 0.04
BIN_OFFSET_SECS = 0.02
NEAREST_TOLERANCE_SECS = 0.08
CONTINUITY_TOLERANCE_SECS = 0.020
HISTORY_SECS = 3.0
RESULT_VALID_SECS = 2.0  # window support end (audio_t0 + 1.0) + 1.0 grace

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AsdWindow:
    stream_id: str
    track_id: int
    audio_t0: float
    pcm16: np.ndarray
    crops: np.ndarray


@dataclass(frozen=True)
class AsdResult:
    stream_id: str
    track_id: int
    audio_t0: float
    probabilities: np.ndarray


class AVBuffer:
    """Bounded audio/video state for one active stream's selected track.

    One packet-rate audio history and one camera-rate crop history, both
    pruned to 3 s.  ``next_window`` returns copies, so a worker can run
    inference outside this lock; it never mutates or blocks on the model.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream_id: str | None = None
        self._track_id: int | None = None
        self._audio: list[tuple[int, float, np.ndarray]] = []  # (seq, t0, samples)
        self._next_seq: int | None = None
        self._next_t0: float | None = None
        self._crops: list[tuple[float, np.ndarray]] = []  # (ts, crop)
        self._last_window_end: float | None = None
        self._result: AsdResult | None = None
        # The audio_t0 of the one window currently issued -- single-worker
        # contract (Task 3): a worker takes the latest window, infers
        # outside this lock, then publishes; a newer next_window() call
        # supersedes an older, still in-flight one by moving this token, so
        # only that newer window's own result can ever land. Any reset
        # (gap, track change, start/stop_stream) clears it to None, which no
        # real result ever matches -- this is what makes "a reset discards
        # late results" hold even across a backward clock step, where a
        # simple floor on audio_t0 could not (the new, correct audio_t0 can
        # be smaller than the stale one).
        self._issued_t0: float | None = None
        # Protocol v2: the backend's locked customer. While set, the track
        # loop crops only this track, even when another face is nearer.
        self._pinned: int | None = None
        # Wakes the ASD worker when audio or a crop arrives, instead of a
        # fixed 80 ms hop. Shares the buffer lock.
        self._input = threading.Condition(self._lock)
        self._publish_listener: Callable[[AsdResult], None] | None = None

    @property
    def active(self) -> bool:
        with self._lock:
            return self._stream_id is not None

    def start_stream(self, stream_id: str) -> None:
        with self._lock:
            self._stream_id = stream_id
            self._reset_locked()

    def stop_stream(self, stream_id: str) -> None:
        with self._lock:
            if stream_id != self._stream_id:
                return
            self._stream_id = None
            self._reset_locked()

    def _reset_locked(self) -> None:
        self._track_id = None
        self._audio.clear()
        self._next_seq = None
        self._next_t0 = None
        self._crops.clear()
        self._last_window_end = None
        self._result = None
        self._issued_t0 = None
        self._pinned = None

    def select_track(self, track_id: int | None) -> None:
        with self._lock:
            if track_id == self._track_id:
                return
            self._track_id = track_id
            self._crops.clear()
            self._result = None
            self._issued_t0 = None  # a reset: any window in flight for the
            # track we're leaving must not land as this one's result.

    @property
    def pinned_track(self) -> int | None:
        with self._lock:
            return self._pinned

    def pin_track(self, track_id: int | None) -> None:
        """Hold ASD on one track (the backend's locked customer); None releases it."""
        with self._lock:
            self._pinned = track_id
        if track_id is not None:
            self.select_track(track_id)

    def wait_for_input(self, timeout: float) -> None:
        """Block until audio or a crop arrives, or *timeout* seconds pass."""
        with self._input:
            self._input.wait(timeout)

    def set_publish_listener(self, listener: Callable[[AsdResult], None] | None) -> None:
        """Called with each published result, on the publishing thread."""
        self._publish_listener = listener

    def push_audio(self, stream_id: str, seq: int, t0: float, pcm16: np.ndarray) -> bool:
        """Accept one 80 ms int16 packet for the current stream.

        Contiguous means seq == previous seq + 1 and the timestamp is within
        20 ms of the previous packet's expected end.  A gap clears history
        and the current result and starts fresh from this packet; the caller
        gets False either way (rejected, or accepted but as a reset).
        """
        with self._lock:
            if (stream_id != self._stream_id or pcm16.shape != (PACKET_SAMPLES,)
                    or pcm16.dtype != np.int16):
                return False
            contiguous = (
                self._next_seq is not None
                and seq == self._next_seq
                and self._next_t0 is not None
                and abs(t0 - self._next_t0) <= CONTINUITY_TOLERANCE_SECS
            )
            if not contiguous:
                self._audio.clear()
                self._result = None
                self._last_window_end = None
                self._issued_t0 = None  # a reset: discard any in-flight window
            self._audio.append((seq, t0, np.array(pcm16, dtype=np.int16, copy=True)))
            self._next_seq = seq + 1
            self._next_t0 = t0 + PACKET_SECS
            self._prune_audio_locked()
            self._input.notify_all()
            return contiguous

    def _prune_audio_locked(self) -> None:
        if not self._audio:
            return
        cutoff = self._audio[-1][1] + PACKET_SECS - HISTORY_SECS
        while len(self._audio) > 1 and self._audio[0][1] + PACKET_SECS <= cutoff:
            self._audio.pop(0)

    def push_crop(self, track_id: int, ts: float, crop: np.ndarray) -> None:
        with self._lock:
            if self._track_id is None or track_id != self._track_id:
                return
            if self._crops and ts <= self._crops[-1][0]:
                # A backward camera-clock step: the ordering pruning relies
                # on no longer holds, so start over rather than risk an
                # unsorted, unbounded history.
                self._crops.clear()
            self._crops.append((ts, np.array(crop, dtype=np.uint8, copy=True)))
            self._input.notify_all()
            cutoff = ts - HISTORY_SECS
            while len(self._crops) > 1 and self._crops[0][0] <= cutoff:
                self._crops.pop(0)

    def next_window(self, *, offset_secs: float, now: float) -> AsdWindow | None:
        """The newest complete 1 s audio window with 25 matching crops, or None.

        Bin *k* is centered at ``audio_t0 + offset_secs + 0.02 + 0.04*k`` and
        must land within 80 ms of a real crop timestamp; a duplicate nearest
        crop is fine, a miss means no window.  Never returns the same
        (unchanged) audio end twice.
        """
        with self._lock:
            if self._stream_id is None or self._track_id is None or not self._audio:
                return None
            total_samples = sum(len(pcm) for _, _, pcm in self._audio)
            if total_samples < WINDOW_SAMPLES:
                return None
            end = self._audio[-1][1] + PACKET_SECS
            if self._last_window_end is not None and end <= self._last_window_end:
                return None
            if not self._crops:
                return None
            audio_t0 = end - WINDOW_SECS
            pcm = np.concatenate([p for _, _, p in self._audio])[-WINDOW_SAMPLES:]

            crop_ts = [ts for ts, _ in self._crops]
            crops_out = []
            for k in range(NUM_BINS):
                center = audio_t0 + offset_secs + BIN_OFFSET_SECS + BIN_STEP_SECS * k
                idx = min(range(len(crop_ts)), key=lambda i: abs(crop_ts[i] - center))
                if abs(crop_ts[idx] - center) > NEAREST_TOLERANCE_SECS:
                    return None
                crops_out.append(self._crops[idx][1])

            self._last_window_end = end
            # This is now the one issued window: only a result computed from
            # exactly this audio_t0 may publish. Calling next_window again
            # before that result arrives moves the token, so a newer take
            # supersedes an older, still in-flight one (the single-worker
            # contract Task 3's worker relies on: take one window, infer
            # outside this lock, publish -- never queue more than one).
            self._issued_t0 = audio_t0
            return AsdWindow(
                self._stream_id, self._track_id, audio_t0,
                pcm.copy(), np.stack(crops_out),
            )

    def publish(self, result: AsdResult) -> bool:
        with self._lock:
            if (result.stream_id != self._stream_id or result.track_id != self._track_id
                    or result.audio_t0 != self._issued_t0):
                return False
            self._result = result
            listener = self._publish_listener
        if listener is not None:
            try:
                listener(result)
            except Exception:  # a listener must never stop the ASD worker
                _log.exception("ASD publish listener failed")
        return True

    def latest_result(self, now: float) -> AsdResult | None:
        with self._lock:
            if self._result is None or now > self._result.audio_t0 + RESULT_VALID_SECS:
                return None
            return self._result

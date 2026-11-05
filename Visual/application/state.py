"""SharedState — what the camera loop and the worker threads share.

The latest frame, the Scene the workers write their observations into, how
long each worker's last pass took, and the running flag.  What is in front of
the kiosk lives in Scene, not here.
"""

import threading
import time
from dataclasses import dataclass

import numpy as np

from Visual.domain.active_speaker import AVBuffer
from Visual.domain.scene import Scene


@dataclass(frozen=True)
class FrameSnapshot:
    """The latest frame together with the camera that made it."""

    frame: np.ndarray | None
    seq: int
    timestamp: float | None
    intrinsics: tuple[float, float, float, float] | None  # None: configured camera
    source: str


class SharedState:
    def __init__(self, mouth_scale: float = 0.06):
        # Frames get their own lock: a 0.9 MB write must not stall readers
        # of the scene or the timings.
        self._frame_lock = threading.Lock()
        self.latest_frame: np.ndarray | None = None
        # Ticks per published frame, so a reader can derive the camera rate.
        self.frame_seq: int = 0
        self._frame_ts: float | None = None
        # Intrinsics of the camera that made the latest frame; None means the
        # configured (calibrated C920) camera.  Set by a remote source.
        self._frame_intrinsics: tuple[float, float, float, float] | None = None
        # Which camera made the latest frame ("local" C920 or "remote").
        self._frame_source = "local"
        self.scene = Scene(mouth_scale=mouth_scale)
        self.asd = AVBuffer()
        # Active-speaker provider: "disabled" (asd_provider none), "ready"
        # (model loaded), "unavailable" (load failed, or inference failed and
        # disabled ASD until a restart).  The WS server answers asd_audio_start
        # with it, so it never needs to know about the provider itself.
        self.asd_status: str = "disabled"
        self._timing_lock = threading.Lock()
        self._timings = {"track": 0.0, "spoof": 0.0, "presence": 0.0}
        self.running: bool = True

    def put_frame(self, frame: np.ndarray, *, timestamp: float | None = None,
                  intrinsics: tuple[float, float, float, float] | None = None,
                  source: str = "local") -> None:
        """Publish a frame. Copies because cap.read() reuses its buffer."""
        snapshot = frame.copy()
        ts = timestamp if timestamp is not None else time.time()
        with self._frame_lock:
            self.latest_frame = snapshot
            self.frame_seq += 1
            self._frame_ts = ts
            self._frame_intrinsics = intrinsics
            self._frame_source = source

    def get_latest_frame(self) -> np.ndarray | None:
        """Return the current frame without copying — consumers only read it.

        Every worker treats the frame as read-only input to a model, so the
        old per-call .copy() was pure waste: the track loop alone pulled
        ~0.9 MB roughly 150 times a second.
        """
        with self._frame_lock:
            return self.latest_frame

    def clear_frame(self, source: str) -> None:
        """Invalidate the previous camera while waiting for the selected source."""
        with self._frame_lock:
            self.latest_frame = None
            self.frame_seq += 1
            self._frame_ts = None
            self._frame_intrinsics = None
            self._frame_source = source

    def get_frame_snapshot(self) -> tuple[np.ndarray, int, float] | None:
        """Return ``(frame, seq, timestamp)`` atomically, or None before the
        first frame. Shares the same array as ``get_latest_frame``."""
        with self._frame_lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame, self.frame_seq, self._frame_ts

    def frame_snapshot(self) -> FrameSnapshot:
        """Frame, seq, timestamp, intrinsics and source under one lock.

        Reading the frame and its intrinsics separately let a camera switch
        land in between, and depth was then scaled with the other camera's
        focal length.
        """
        with self._frame_lock:
            return FrameSnapshot(self.latest_frame, self.frame_seq, self._frame_ts,
                                 self._frame_intrinsics, self._frame_source)

    def frame_intrinsics(self) -> tuple[float, float, float, float] | None:
        """``(fx, fy, cx, cy)`` of the latest frame's camera, or None for the
        configured camera."""
        with self._frame_lock:
            return self._frame_intrinsics

    def frame_source(self) -> str:
        """The camera that made the latest frame: ``"local"`` or ``"remote"``."""
        with self._frame_lock:
            return self._frame_source

    def set_timing(self, worker: str, ms: float) -> None:
        """Record how long *worker*'s last pass took (``track``/``spoof``/``presence``)."""
        with self._timing_lock:
            self._timings[worker] = ms

    def timings(self) -> dict:
        with self._timing_lock:
            return dict(self._timings)

"""CameraRouter: which camera's frames reach SharedState.

The local C920 is the source.  A voice session may explicitly select its own
remote WebRTC camera; only then, and only while that camera keeps delivering,
do its frames replace the C920's.  The C920 loop never stops reading, so when
the remote session ends or its frames stop for ``stale_after_secs`` the next
C920 frame is published -- one frame interval of fallback.

A remote takes over (and takes over again after a fallback) only once
``steady_frames`` frames have arrived each within ``stale_after_secs`` of the
last.  A remote that delivers sparsely -- a browser tab in the background is
throttled to about one frame a second -- therefore never flips the image back
and forth; the C920 keeps the camera until the remote is steady again.

Kiosk callers set ``prefer_local=True``: fresh local frames take priority over
any selected remote stream. Remote remains warm and takes over only when local
frames stop; a recovered local camera takes priority immediately. A selected
session can opt into ``prefer_remote`` to use its laptop/phone camera while the
local camera remains healthy; expiry and release still fall back to local.

An explicit ``camera_source`` pins that source until release. Missing device
frames do not permit local frames to replace them. Legacy callers that omit
the source retain the fallback behavior described above.

Every source leaves as one canonical frame: BGR uint8 at the configured
capture size.  Remote frames carry intrinsics estimated from a field of view
(an uncalibrated phone or laptop camera); local frames carry none, so the
workers keep using the C920 calibration exactly as before.
"""

import logging
import math
import threading
import time
from typing import Callable

import cv2
import numpy as np

from Visual.application.state import SharedState

_log = logging.getLogger(__name__)

Intrinsics = tuple[float, float, float, float]   # fx, fy, cx, cy


def estimate_intrinsics(width: int, height: int, hfov_deg: float) -> Intrinsics:
    """Pinhole intrinsics for a *width* x *height* frame with horizontal FOV *hfov_deg*."""
    fx = (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    return (fx, fx, width / 2.0, height / 2.0)


def normalize_frame(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    """Centre-crop *frame* to the canonical aspect, then resize to *width* x *height*.

    Cropping, not letterboxing or stretching, keeps faces undistorted and the
    pinhole model valid.  A frame already canonical is returned as is.
    """
    h, w = frame.shape[:2]
    if (w, h) == (width, height):
        return frame
    target = width / height
    if w / h > target:
        crop = int(round(h * target))
        x0 = (w - crop) // 2
        frame = frame[:, x0:x0 + crop]
    elif w / h < target:
        crop = int(round(w / target))
        y0 = (h - crop) // 2
        frame = frame[y0:y0 + crop, :]
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


class CameraRouter:
    def __init__(self, state: SharedState, *, width: int, height: int,
                 remote_hfov_deg: float, stale_after_secs: float = 0.5,
                 steady_frames: int = 5,
                 clock: Callable[[], float] = time.monotonic, prefer_local: bool = False):
        self._state = state
        self._width, self._height = width, height
        self._remote_intrinsics = estimate_intrinsics(width, height, remote_hfov_deg)
        self._stale = stale_after_secs
        self._steady = max(1, steady_frames)
        self._prefer_local = prefer_local
        self._remote_preferred = False
        self._selected_camera: str | None = None
        self._local_seen: float | None = None
        self._clock = clock
        self._lock = threading.Lock()
        self._remote_stream: str | None = None
        self._remote_seen: float | None = None
        self._remote_run = 0          # consecutive frames, each in time
        self._source = "local"

    @property
    def local_available(self) -> bool:
        with self._lock:
            return self._local_seen is not None and self._clock() - self._local_seen < self._stale

    @property
    def source(self) -> str:
        with self._lock:
            if self._selected_camera is not None:
                return "remote" if self._selected_camera == "device" else "local"
            return "remote" if self._remote_live() else "local"

    def _remote_live(self) -> bool:
        if self._selected_camera == "local":
            return False
        local_live = (self._prefer_local and not self._remote_preferred and self._local_seen is not None
                      and self._clock() - self._local_seen < self._stale)
        return (not local_live and self._remote_stream is not None and self._remote_seen is not None
                and self._remote_run >= self._steady
                and self._clock() - self._remote_seen < self._stale)

    def _switch(self, source: str, reason: str) -> None:
        if source != self._source:
            _log.warning("[camera] source %s -> %s (%s)", self._source, source, reason)
            self._source = source

    def local_frame(self, frame: np.ndarray, timestamp: float) -> bool:
        """Publish a C920 frame unless a live remote camera is selected."""
        with self._lock:
            self._local_seen = self._clock()
            if self._selected_camera == "device" or self._remote_live():
                return False
            if self._source == "remote":
                self._switch("local", "local camera available" if self._prefer_local else "remote frames stopped")
            self._state.put_frame(frame, timestamp=timestamp)
        return True

    def select_remote(self, stream_id: str, *, prefer_remote: bool = False,
                      camera_source: str | None = None) -> None:
        """A session explicitly asks for its own camera."""
        if camera_source not in (None, "local", "device"):
            raise ValueError("invalid_camera_source")
        with self._lock:
            self._remote_stream, self._remote_seen = stream_id, None
            self._remote_preferred = prefer_remote
            self._remote_run = 0
            self._selected_camera = camera_source
            if camera_source is not None:
                self._state.clear_frame("remote" if camera_source == "device" else "local")
                self._state.scene.reset()

    def remote_frame(self, stream_id: str, frame: np.ndarray, timestamp: float) -> bool:
        """Publish a frame from the selected remote camera; others are ignored."""
        with self._lock:
            if stream_id != self._remote_stream or self._selected_camera == "local":
                return False
            now = self._clock()
            steady = self._remote_seen is not None and now - self._remote_seen < self._stale
            self._remote_run = self._remote_run + 1 if steady else 1
            self._remote_seen = now
            if self._selected_camera != "device" and not self._remote_live():
                return False
            self._switch("remote", f"stream {stream_id}")
            self._state.put_frame(normalize_frame(frame, self._width, self._height),
                                  timestamp=timestamp, intrinsics=self._remote_intrinsics,
                                  source="remote")
        return True

    def release_remote(self, stream_id: str) -> None:
        """The session ended or disconnected: the C920 takes over at once."""
        with self._lock:
            if stream_id != self._remote_stream:
                return
            self._remote_stream, self._remote_seen = None, None
            self._remote_preferred = False
            self._selected_camera = None
            self._remote_run = 0
            self._switch("local", f"stream {stream_id} released")

"""A standing clip for the moments Trend is silent, and the dissolve into and out of it."""

import threading

import cv2
import numpy as np


def rest_frame_index(elapsed, fps, count):
    """Forward then backward through the clip, so its end never jumps to its start."""
    if count <= 1:
        return 0
    period = 2 * (count - 1)
    position = int(elapsed * fps + 1e-9) % period
    return position if position < count else period - position


def load_rest_clip(path, size):
    """RGB frames at the engine's (height, width), plus the clip's own frame rate."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Ditto rest video missing or unreadable: {path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    height, width = size
    frames = []
    while True:
        ok, bgr = capture.read()
        if not ok:
            break
        if bgr.shape[:2] != (height, width):
            bgr = cv2.resize(bgr, (width, height), interpolation=cv2.INTER_AREA)
        frames.append(np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
    capture.release()
    if not frames:
        raise ValueError("Ditto rest video has no frames")
    return frames, float(fps)


class CrossFade:
    """Dissolve from the last frame shown whenever the kind of picture changes."""

    def __init__(self, seconds):
        self._seconds = float(seconds)
        self._lock = threading.Lock()
        self.clear()

    def clear(self):
        with self._lock:
            self._mode = self._last = self._from = None
            self._at = 0.0

    def apply(self, frame, mode, now):
        with self._lock:
            if mode != self._mode:
                if self._mode is not None and self._last is not None:
                    self._from, self._at = self._last, now
                self._mode = mode
            result = frame
            if self._from is not None and self._seconds <= 0:
                self._from = None  # A cut: two different clips overlaid show a double image.
            if self._from is not None:
                weight = (now - self._at) / self._seconds
                if weight >= 1:
                    self._from = None
                else:
                    weight = max(0.0, weight)
                    result = cv2.addWeighted(self._from, 1 - weight, frame, weight, 0)
            self._last = result
            return result

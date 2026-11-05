"""Mouth activity: is a tracked face talking?

The lip opening (inner-lip gap over inner-lip width) barely changes when a
head turns or nods, but opens and closes several times a second in speech.
Its spread over the last half second, scaled to [0, 1], is the activity.
Measured on the laptop webcam: std 0.002 silent, 0.011 silent while shaking
the head, 0.061 talking; ``scale`` = 0.06 puts talking near 1.0.
"""
from __future__ import annotations

import statistics
from collections import deque


class MouthActivity:
    """Per-track rolling lip openings.  Not thread-safe: the Scene locks it."""

    def __init__(self, window_s: float = 0.5, scale: float = 0.06):
        self._window = window_s
        self._scale = scale
        self._samples: dict[int, deque] = {}

    def update(self, track_id: int, opening: float, t: float) -> None:
        samples = self._samples.setdefault(int(track_id), deque())
        samples.append((t, float(opening)))
        while samples and samples[0][0] < t - self._window:
            samples.popleft()

    def activity(self, track_id: int) -> float | None:
        samples = self._samples.get(int(track_id))
        if not samples or len(samples) < 2:
            return None
        spread = statistics.pstdev(value for _, value in samples)
        return min(1.0, spread / self._scale)

    def retain(self, track_ids: set[int]) -> None:
        for tid in list(self._samples):
            if tid not in track_ids:
                del self._samples[tid]

"""Bounded motion trajectories timed against received 16kHz audio samples.

Ditto's streaming Hubert features have 80ms of received right context. A motion
frame is timestamped at the end of its 40ms feature interval, before that context.
Interpolation uses existing numeric motion only; it does not predict future speech.
"""

from bisect import bisect_left
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PoseSample:
    sample: float
    drive: dict[str, np.ndarray]


def _blend(left, right, alpha):
    return {key: left[key] * (1 - alpha) + right[key] * alpha for key in left}


class PoseTimeline:
    def __init__(self, capacity=160):
        if capacity < 2:
            raise ValueError("Motion capacity must retain at least two poses")
        self.capacity = capacity
        self.dropped = 0
        self._poses = []

    def __len__(self):
        return len(self._poses)

    def clear(self):
        self._poses.clear()
        self.dropped = 0

    def append(self, drives, *, end_sample):
        if not drives:
            return
        # Windows can advance three, four or five 40ms frames. Fuse their recent
        # overlapping poses and retain older history; never replay a whole window.
        previous = {pose.sample: pose.drive for pose in self._poses}
        previous_end = self._poses[-1].sample if self._poses else None
        for index, drive in enumerate(drives):
            sample = end_sample - 1280 - (len(drives) - 1 - index) * 640
            copied = {key: np.array(value, copy=True) for key, value in drive.items()}
            if sample in previous:
                alpha = max(0.0, min(1.0, (sample - (previous_end - 2560)) / 2560))
                copied = _blend(previous[sample], copied, alpha)
            previous[sample] = copied
        combined = [PoseSample(sample, previous[sample]) for sample in sorted(previous)]
        self.dropped += max(0, len(combined) - self.capacity)
        self._poses = combined[-self.capacity :]

    def at(self, sample):
        if not self._poses:
            return None
        position = bisect_left([pose.sample for pose in self._poses], sample)
        if position == 0:
            return self._poses[0]
        if position == len(self._poses):
            return self._poses[-1]
        left, right = self._poses[position - 1], self._poses[position]
        alpha = (sample - left.sample) / (right.sample - left.sample)
        return PoseSample(sample, _blend(left.drive, right.drive, alpha))

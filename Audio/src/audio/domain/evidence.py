"""Vision's recent face tracks, pushed active-speaker windows and audio spans."""

from __future__ import annotations

import copy
import math
import threading
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

# Vision samples mouths at 10 Hz and scores the last 0.5 s, so an audio frame
# is judged by the customer's mouth within 0.3 s either side of it.
VISION_WINDOW_SECS = 0.3


class FaceTrackBuffer:
    """The last few seconds of Vision's ``faces`` events (spec §5.2)."""

    def __init__(self, history_s: float = 3.0) -> None:
        self._history = history_s
        self._events: deque[dict] = deque()
        self._lock = threading.Lock()
        self._asd_stream: str | None = None
        # Protocol v2: ASD windows pushed by Vision as their own events.
        self._asd_windows: deque[dict] = deque()
        self._asd_pushed = False

    def set_asd_stream(self, stream_id: str | None) -> None:
        """Invalidate ASD scores while retaining face and mouth history."""
        with self._lock:
            self._asd_stream = stream_id
            self._asd_windows.clear()
            for event in self._events:
                for track in event.get("tracks", ()):
                    track.pop("asd", None)

    def asd_stream_matches(self, stream_id: str) -> bool:
        with self._lock:
            return stream_id == self._asd_stream

    def use_pushed_asd(self, pushed: bool) -> None:
        """v2: read ASD from pushed windows and ignore the faces-event field."""
        with self._lock:
            self._asd_pushed = pushed
            self._asd_windows.clear()

    def add_asd(self, window: dict) -> None:
        """One pushed ASD window for the current stream (older ones pruned)."""
        t0 = window.get("t0")
        if (
            isinstance(t0, bool)
            or not isinstance(t0, (int, float))
            or not math.isfinite(t0)
        ):
            return
        with self._lock:
            if window.get("stream_id") != self._asd_stream:
                return
            self._asd_windows.append(dict(window))
            while self._asd_windows and self._asd_windows[0]["t0"] < t0 - self._history:
                self._asd_windows.popleft()

    def tracks_at(self, t: float) -> list[dict]:
        """The tracks of the faces event nearest to *t*."""
        with self._lock:
            if not self._events:
                return []
            event = min(self._events, key=lambda e: abs(e["ts"] - t))
            return [dict(f) for f in event.get("tracks", ())]

    def present(self, track_id: int, t0: float, t1: float) -> bool:
        with self._lock:
            return any(
                f.get("track_id") == track_id
                for e in self._events
                if t0 <= e["ts"] <= t1
                for f in e.get("tracks", ())
            )

    def snapshot(self, *, include_asd: bool = True) -> FaceTrackBuffer:
        """Freeze current evidence before yielding row verdicts downstream."""
        snapshot = FaceTrackBuffer(self._history)
        with self._lock:
            snapshot._events = copy.deepcopy(self._events)
            snapshot._asd_stream = self._asd_stream
            snapshot._asd_windows = copy.deepcopy(self._asd_windows)
            snapshot._asd_pushed = self._asd_pushed
        if not include_asd:
            snapshot._asd_windows.clear()
            for event in snapshot._events:
                for track in event.get("tracks", ()):
                    track.pop("asd", None)
        return snapshot

    def add(self, event: dict) -> None:
        with self._lock:
            self._events.append(event)
            newest = event.get("ts", 0.0)
            while (
                self._events and self._events[0].get("ts", 0.0) < newest - self._history
            ):
                self._events.popleft()

    def fresh(self, now: float, max_age: float = 1.0) -> bool:
        with self._lock:
            return bool(self._events) and now - self._events[-1]["ts"] <= max_age

    def anchor(self, t: float, max_m: float) -> int | None:
        with self._lock:
            if not self._events:
                return None
            event = min(self._events, key=lambda e: abs(e["ts"] - t))
        near = [
            (f["distance_m"], f["track_id"])
            for f in event.get("tracks", ())
            if f.get("distance_m") is not None and f["distance_m"] <= max_m
        ]
        return min(near)[1] if near else None

    def mouth(self, track_id: int, t0: float, t1: float) -> float | None:
        with self._lock:
            values = [
                f["mouth_activity"]
                for e in self._events
                if t0 <= e["ts"] <= t1
                for f in e.get("tracks", ())
                if f["track_id"] == track_id and f.get("mouth_activity") is not None
            ]
        # Mean, not max: one noisy sample (a glance, a nod) must not read as
        # the customer talking for the whole window.
        return sum(values) / len(values) if values else None

    def active_speaker(
        self, track_id: int, t0: float, t1: float, *, stream_id: str, now: float
    ) -> float | None:
        """Mean of the current stream's newest complete 25-bin ASD window."""
        if not stream_id or not all(map(math.isfinite, (t0, t1, now))) or t1 <= t0:
            return None
        with self._lock:
            if stream_id != self._asd_stream:
                return None
            if self._asd_pushed:
                windows = [
                    dict(w) for w in self._asd_windows if w.get("track_id") == track_id
                ]
            else:
                windows = [
                    dict(f["asd"])
                    for event in self._events
                    for f in event.get("tracks", ())
                    if f.get("track_id") == track_id and isinstance(f.get("asd"), dict)
                ]
        valid: list[tuple[float, Sequence[float]]] = []
        for window in windows:
            if not isinstance(window, dict) or window.get("stream_id") != stream_id:
                continue
            start, frame_secs, values = (
                window.get("t0"),
                window.get("frame_secs"),
                window.get("probabilities"),
            )
            if (
                isinstance(start, bool)
                or not isinstance(start, (int, float))
                or not math.isfinite(start)
                or isinstance(frame_secs, bool)
                or not isinstance(frame_secs, (int, float))
                or not math.isfinite(frame_secs)
                or abs(frame_secs - 0.04) > 1e-6
                or not isinstance(values, (list, tuple))
                or len(values) != 25
                or any(
                    isinstance(p, bool)
                    or not isinstance(p, (int, float))
                    or not math.isfinite(p)
                    or not 0 <= p <= 1
                    for p in values
                )
            ):
                continue
            end = start + 1.0
            # 1 ms slack: Vision's window end and this chunk end are separate
            # float sums of the same samples at Unix-second magnitudes.
            if start <= t0 + 1e-3 and t1 <= end + 1e-3 and now - end <= 1.0:
                valid.append((start, values))
        if not valid:
            return None
        start, values = max(valid, key=lambda item: item[0])
        weighted = sum(
            p * max(0.0, min(t1, start + (i + 1) * 0.04) - max(t0, start + i * 0.04))
            for i, p in enumerate(values)
        )
        with self._lock:
            return weighted / (t1 - t0) if stream_id == self._asd_stream else None


@dataclass(frozen=True)
class AudioSpan:
    start: float
    end: float
    stream_id: str | None

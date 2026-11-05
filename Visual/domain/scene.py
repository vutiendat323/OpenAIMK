"""Scene — who is in front of the kiosk, measured once, read everywhere.

The worker threads push raw observations in (faces from the track loop, bodies
from the presence loop, spoof tags from the spoof loop).  Readers take an
immutable ``SceneSnapshot``: every person with a smoothed distance, *the*
nearest one, and body presence.  Choosing the nearest face, smoothing its
distance, attaching a body to a face and turning all of it into the kiosk
event happen here and nowhere else -- they used to be re-derived by the main
loop, the server and the console, and drifted apart (the presence event once
paired the nearest distance with the id of whichever track was listed first).
"""

from __future__ import annotations

import math
import statistics
import threading
import time
from dataclasses import dataclass

from Visual.domain.geometry import box_contains_center
from Visual.domain.mouth import MouthActivity


@dataclass(frozen=True)
class Person:
    """One tracked face, as the kiosk should see it."""

    id: int
    box: tuple                  # (x1, y1, x2, y2), frame pixels
    dist: float                 # smoothed metres; -1.0 until the first reading
    raw: float | None           # this update's PnP reading, before smoothing
    kps: tuple | None           # five landmarks, when detected this update
    gate: bool | None           # True measured, False rejected, None coasting
    spoof: float | None         # spoof score, once the spoof loop has run
    spoof_flag: bool | None
    body_m: float | None        # the body this face sits in, if one was seen
    mouth: float | None = None  # mouth activity 0..1, once the lip reader has run


@dataclass(frozen=True)
class SceneSnapshot:
    people: tuple               # Person, in tracker order
    nearest: Person | None      # nearest measured face, else the first face
    body_m: float               # nearest body, -1.0 when none is seen
    facing: bool                # some face has a distance
    bodies: tuple               # ({"box": ..., "dist": ...}, ...)
    face_frame_seq: int = -1
    face_captured_at: float | None = None
    spoof_captured_at: float | None = None

    def event(self, ts: float) -> dict:
        """The presence event the kiosk consumes.

        Three kinds, unchanged for clients that only read them: no_person,
        person_unknown (a face, no distance yet), person_near.  Every kind
        also carries body_m and facing, so the kiosk can tell "looked away"
        from "walked off".
        """
        presence = {"body_m": self.body_m, "facing": self.facing,
                    "tracks": [{"track_id": p.id,
                                "distance_m": round(p.dist, 2) if p.dist > 0 else None,
                                "body_m": p.body_m} for p in self.people]}
        if self.nearest is None:
            return {"event": "no_person", "ts": ts, **presence}
        if self.nearest.dist <= 0:
            return {"event": "person_unknown", "ts": ts, "track_count": len(self.people),
                    "track_id": self.nearest.id, **presence}
        return {"event": "person_near", "ts": ts, "nearest_m": round(self.nearest.dist, 2),
                "track_id": self.nearest.id, **presence}


class _Smoother:
    """Median-of-3, then a position-only Kalman filter.

    Median, not an EMA: a single bad sample (a landmark glitch, an id that
    jumped faces) is dropped outright instead of decaying through the output
    (an EMA at alpha=0.25 held one for 5-7 s), and a real change gets through
    on its second sample.  Position only: people walk then stop, and a
    constant-velocity model overshot a stop at 0.50 m to 0.36 m.  Process
    noise accrues per second, so smoothing no longer depends on how often
    anything polls it.
    """

    def __init__(self, first: float, t: float, measurement_noise: float, process_noise_per_s: float):
        self.value, self._p, self._t = first, 1.0, t
        self._recent = [first]
        self._r, self._q = measurement_noise, process_noise_per_s

    def update(self, z: float, t: float) -> float:
        self._recent = (self._recent + [z])[-3:]
        med = statistics.median(self._recent)
        self._p += self._q * max(0.0, t - self._t)
        gain = self._p / (self._p + self._r)
        self.value += gain * (med - self.value)
        self._p *= 1.0 - gain
        self._t = t
        return self.value


class Scene:
    """Thread-safe: the three worker threads write, the server reads."""

    # 0.03 per call at the old 30 fps call rate: the behaviour the kiosk was
    # tuned on, now expressed per second so it survives any polling rate.
    MEASUREMENT_NOISE = 0.03
    PROCESS_NOISE_PER_S = 0.9
    # Bodies older than this are no longer evidence: a presence worker that
    # keeps failing must not hold a kiosk session open with its last reading.
    BODY_MAX_AGE_SEC = 3.0

    def __init__(self, measurement_noise: float = MEASUREMENT_NOISE,
                 process_noise_per_s: float = PROCESS_NOISE_PER_S,
                 mouth_scale: float = 0.06,
                 body_max_age_sec: float = BODY_MAX_AGE_SEC):
        self._lock = threading.Lock()
        self._body_max_age = body_max_age_sec
        self._bodies_t = 0.0
        # Bumped by reset(): a reading taken before a camera switch carries
        # the old value and is dropped.
        self.generation = 0
        self._r, self._q = measurement_noise, process_noise_per_s
        self._tracks: list = []
        self._raw: dict = {}
        self._kps: dict = {}
        self._smoothers: dict[int, _Smoother] = {}
        self._spoof: dict = {}
        self._bodies: list = []
        self._face_frame_seq = -1
        self._face_captured_at = self._spoof_captured_at = None
        self._mouth = MouthActivity(scale=mouth_scale)

    # -- writers -------------------------------------------------------------

    def reset(self) -> None:
        """Forget every observation: the camera they came from is gone."""
        with self._lock:
            self.generation += 1
            self._tracks, self._raw, self._kps = [], {}, {}
            self._smoothers.clear()
            self._spoof, self._bodies = {}, []
            self._face_frame_seq = -1
            self._face_captured_at = self._spoof_captured_at = None
            self._mouth.retain(set())

    def observe_faces(self, tracks, raw: dict, landmarks: dict, t: float | None = None, *,
                      frame_seq: int = -1, captured_at: float | None = None) -> None:
        """One tracker update: its tracks, their PnP readings and landmarks.

        *raw* holds a reading only for faces PnP accepted; a face in
        *landmarks* but not in *raw* was gated out and keeps its last value.
        """
        t = time.monotonic() if t is None else t
        with self._lock:
            ids = {int(tr[4]) for tr in tracks}
            for tid in list(self._smoothers):
                if tid not in ids:
                    del self._smoothers[tid]
            self._mouth.retain(ids)
            valid = {int(k): float(v) for k, v in raw.items()
                     if v is not None and math.isfinite(v)}
            for tid, z in valid.items():
                if tid in self._smoothers:
                    self._smoothers[tid].update(z, t)
                elif tid in ids:
                    self._smoothers[tid] = _Smoother(z, t, self._r, self._q)
            self._face_frame_seq, self._face_captured_at = frame_seq, captured_at
            self._tracks = list(tracks)
            self._raw = valid
            self._kps = {int(k): tuple(tuple(p) for p in v) for k, v in landmarks.items()}

    def observe_mouths(self, openings: dict, t: float | None = None) -> None:
        """One lip-reader pass: ``{track_id: lip opening}`` for faces seen this update."""
        t = time.monotonic() if t is None else t
        with self._lock:
            for tid, opening in openings.items():
                self._mouth.update(int(tid), float(opening), t)

    def observe_bodies(self, bodies, generation: int | None = None,
                       t: float | None = None) -> None:
        """One presence tick: person boxes with their metres.

        *generation* is ``self.generation`` read before the tick's frame; a
        reset since then means the boxes came from a camera that is gone.
        """
        t = time.monotonic() if t is None else t
        with self._lock:
            if generation is not None and generation != self.generation:
                return
            self._bodies = [{"box": tuple(b["box"]), "dist": float(b["dist"])} for b in bodies]
            self._bodies_t = t

    def observe_spoof(self, tags: dict, *, captured_at: float | None = None, generation: int | None = None) -> None:
        """One spoof tick: ``{track_id: (is_spoof, score)}``."""
        with self._lock:
            if generation is not None and generation != self.generation:
                return
            self._spoof_captured_at = captured_at
            self._spoof = {int(k): (bool(v[0]), float(v[1])) for k, v in tags.items()}

    # -- reader --------------------------------------------------------------

    def snapshot(self, t: float | None = None) -> SceneSnapshot:
        t = time.monotonic() if t is None else t
        with self._lock:
            fresh = t - self._bodies_t <= self._body_max_age
            live_bodies = self._bodies if fresh else []
            people = []
            for x1, y1, x2, y2, tid, _conf in self._tracks:
                tid = int(tid)
                box = (float(x1), float(y1), float(x2), float(y2))
                kps = self._kps.get(tid)
                spoof = self._spoof.get(tid)
                body = next((b for b in live_bodies if box_contains_center(b["box"], box)), None)
                smoother = self._smoothers.get(tid)
                people.append(Person(
                    id=tid, box=box,
                    dist=smoother.value if smoother else -1.0,
                    raw=self._raw.get(tid),
                    kps=kps,
                    gate=None if kps is None else tid in self._raw,
                    spoof=None if spoof is None else spoof[1],
                    spoof_flag=None if spoof is None else spoof[0],
                    body_m=None if body is None else body["dist"],
                    mouth=self._mouth.activity(tid),
                ))
            bodies = tuple(dict(b) for b in live_bodies)
            face_frame_seq, face_captured_at = self._face_frame_seq, self._face_captured_at
            spoof_captured_at = self._spoof_captured_at

        measured = [p for p in people if p.dist > 0]
        nearest = min(measured, key=lambda p: p.dist) if measured else (people[0] if people else None)
        body_dists = [b["dist"] for b in bodies if b["dist"] > 0]
        return SceneSnapshot(
            people=tuple(people),
            nearest=nearest,
            body_m=round(min(body_dists), 2) if body_dists else -1.0,
            facing=bool(measured),
            bodies=bodies,
            face_frame_seq=face_frame_seq, face_captured_at=face_captured_at,
            spoof_captured_at=spoof_captured_at,
        )

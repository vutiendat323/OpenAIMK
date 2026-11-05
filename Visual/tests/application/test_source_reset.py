"""Switching camera source wipes what the old camera left behind.

Live 2026-10-03: after a switch back to the C920, the remote camera's face box
(0.38 m) stayed drawn over the empty office.  Tracks, smoothed distances,
mouths, spoof tags and bodies all belong to one camera; on a source change the
tracker and the Scene start clean.  Track ids keep counting up, so an id the
backend locked onto is never reused for a different person.
"""

import threading
import time

import numpy as np

from tests.application.test_pipeline import _cfg, _Faces
from Visual.application import track_faces
from Visual.application.camera_router import CameraRouter
from Visual.application.state import SharedState
from Visual.domain.scene import Scene
from Visual.infrastructure.faces.bytetrack import ByteTrack


def _frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


def test_frames_carry_their_source():
    state = SharedState()
    state.put_frame(_frame())
    assert state.frame_source() == "local"
    state.put_frame(_frame(), source="remote")
    assert state.frame_source() == "remote"


def test_router_tags_each_source():
    state = SharedState()
    router = CameraRouter(state, width=640, height=480, remote_hfov_deg=70.0,
                          steady_frames=1)
    router.local_frame(_frame(), 1.0)
    assert state.frame_source() == "local"
    router.select_remote("s1")
    router.remote_frame("s1", _frame(), 2.0)
    assert state.frame_source() == "remote"


def test_scene_reset_forgets_every_observation():
    scene = Scene()
    scene.observe_faces([(0, 0, 50, 60, 1, 0.9)], raw={1: 0.6},
                        landmarks={1: [[1.0, 1.0]] * 5}, t=0.0)
    scene.observe_bodies([{"box": (0, 0, 100, 400), "dist": 0.8}])
    scene.observe_spoof({1: (False, 0.1)})

    scene.reset()

    snap = scene.snapshot()
    assert snap.people == () and snap.nearest is None and snap.body_m == -1.0


def test_tracker_clear_drops_tracks_but_never_reuses_ids():
    tracker = ByteTrack(15, 0.5, 0.3, 0.5, 0.7)
    box = [(100.0, 100.0, 200.0, 220.0, 0.95)]
    for _ in range(3):
        tracker.update(box)
    first_ids = {t.id for t in tracker.active_tracks}

    tracker.clear()
    assert tracker.active_tracks == []
    for _ in range(3):
        tracker.update(box)
    assert first_ids.isdisjoint({t.id for t in tracker.active_tracks})


class _RecordingTracker(ByteTrack):
    def __init__(self):
        super().__init__(15, 0.5, 0.3, 0.5, 0.7)
        self.clears = 0

    def clear(self):
        self.clears += 1
        super().clear()


def test_track_loop_starts_clean_when_the_source_changes():
    state = SharedState()
    state.put_frame(_frame())
    tracker = _RecordingTracker()
    thread = threading.Thread(target=track_faces._track_loop,
                              args=(state, _cfg(), _Faces(), tracker, None), daemon=True)
    thread.start()
    try:
        _wait(lambda: state.scene.snapshot().people)
        assert tracker.clears == 0

        state.put_frame(_frame(), source="remote")
        _wait(lambda: tracker.clears == 1)
        state.put_frame(_frame())
        _wait(lambda: tracker.clears == 2)
    finally:
        state.running = False
        thread.join(timeout=2.0)


def _wait(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "condition never held"
        time.sleep(0.01)

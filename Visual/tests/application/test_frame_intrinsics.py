"""Workers measure each frame with the intrinsics of the camera that made it:
the C920 calibration for local frames, the estimate for a remote camera."""

import threading
import time

import numpy as np
import pytest

from tests.application.test_pipeline import FX, _cfg, _Faces
from Visual.application import track_faces
from Visual.application.measure_presence import _presence_loop
from Visual.application.state import SharedState
from Visual.infrastructure.faces.bytetrack import ByteTrack

REMOTE = (400.0, 400.0, 320.0, 240.0)


def _frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


class TestSharedStateIntrinsics:
    def test_local_frames_carry_no_override(self):
        state = SharedState()
        state.put_frame(_frame())
        assert state.frame_intrinsics() is None

    def test_intrinsics_follow_the_latest_frame(self):
        state = SharedState()
        state.put_frame(_frame(), intrinsics=REMOTE)
        assert state.frame_intrinsics() == REMOTE
        state.put_frame(_frame())
        assert state.frame_intrinsics() is None


class _Depth:
    def __init__(self, state):
        self.state = state
        self.calls = []

    def estimate(self, rgb, intrinsics, scale):
        self.calls.append((intrinsics, scale))
        self.state.running = False
        return np.ones(rgb.shape[:2], dtype=np.float32)


def _presence_call(intrinsics):
    state = SharedState()
    state.put_frame(_frame(), intrinsics=intrinsics)
    depth = _Depth(state)
    _presence_loop(state, _cfg(), depth)
    return depth.calls[0]


class TestPresence:
    def test_local_frames_use_the_configured_calibration(self):
        assert _presence_call(None) == ((FX, FX, 320.0, 240.0), FX / 1000.0)

    def test_remote_frames_use_their_own_intrinsics_and_scale(self):
        intrinsics, scale = _presence_call(REMOTE)
        assert intrinsics == REMOTE
        assert scale == pytest.approx(400.0 / 1000.0)


def _track_matrices(monkeypatch, intrinsics):
    state = SharedState()
    state.put_frame(_frame(), intrinsics=intrinsics)
    seen = []

    def spy(landmarks, camera_matrix, ipd):
        seen.append(camera_matrix.copy())
        state.running = False
        return None

    monkeypatch.setattr(track_faces, "face_distance", spy)
    thread = threading.Thread(
        target=track_faces._track_loop,
        args=(state, _cfg(), _Faces(), ByteTrack(15, 0.5, 0.3, 0.5, 0.7), None),
        daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 5.0
    while not seen and time.monotonic() < deadline:
        time.sleep(0.01)
    state.running = False
    thread.join(timeout=2.0)
    assert seen, "track loop never measured a face"
    return seen[0]


class TestTrack:
    def test_local_frames_use_the_configured_calibration(self, monkeypatch):
        matrix = _track_matrices(monkeypatch, None)
        assert (matrix[0, 0], matrix[1, 1], matrix[0, 2], matrix[1, 2]) == (
            FX, FX, 320.0, 240.0)

    def test_remote_frames_use_their_own_intrinsics(self, monkeypatch):
        matrix = _track_matrices(monkeypatch, REMOTE)
        assert (matrix[0, 0], matrix[1, 1], matrix[0, 2], matrix[1, 2]) == REMOTE

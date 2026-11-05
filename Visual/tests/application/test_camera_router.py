"""CameraRouter: the local C920 is the source unless a session explicitly
selects its remote WebRTC camera, and a lost remote falls straight back."""

import math

import numpy as np
import pytest

from Visual.application.camera_router import (
    CameraRouter,
    estimate_intrinsics,
    normalize_frame,
)
from Visual.application.state import SharedState


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _router(clock=None, stale=0.5, steady=1):
    state = SharedState()
    router = CameraRouter(state, width=640, height=480, remote_hfov_deg=70.0,
                          stale_after_secs=stale, steady_frames=steady,
                          clock=clock or _Clock())
    return state, router


def _local(value=1):
    return np.full((480, 640, 3), value, dtype=np.uint8)


def _remote(value=2, w=1280, h=720):
    return np.full((h, w, 3), value, dtype=np.uint8)


class TestDefaultLocal:
    def test_local_frames_are_published_unchanged_with_configured_intrinsics(self):
        state, router = _router()
        frame = _local(7)

        assert router.local_frame(frame, 1000.0)

        published, seq, ts = state.get_frame_snapshot()
        assert np.array_equal(published, frame) and seq == 1 and ts == 1000.0
        assert state.frame_intrinsics() is None  # workers use the C920 calibration
        assert router.source == "local"

    def test_remote_frames_are_ignored_until_a_session_selects_them(self):
        state, router = _router()

        assert not router.remote_frame("s1", _remote(), 1000.0)

        assert state.get_frame_snapshot() is None
        assert router.source == "local"


class TestExplicitRemote:
    def test_selected_remote_replaces_local_frames(self):
        state, router = _router()
        router.select_remote("s1")

        assert router.remote_frame("s1", _remote(9), 1000.5)
        assert not router.local_frame(_local(1), 1000.6)

        frame, seq, ts = state.get_frame_snapshot()
        assert frame.shape == (480, 640, 3) and int(frame[0, 0, 0]) == 9
        assert seq == 1 and ts == 1000.5  # remote keeps its own timestamp
        assert state.frame_intrinsics() == pytest.approx(estimate_intrinsics(640, 480, 70.0))
        assert router.source == "remote"

    def test_local_keeps_publishing_until_the_first_remote_frame_arrives(self):
        state, router = _router()
        router.select_remote("s1")

        assert router.local_frame(_local(3), 1000.0)
        assert router.source == "local"

    def test_another_stream_cannot_publish(self):
        state, router = _router()
        router.select_remote("s1")

        assert not router.remote_frame("s2", _remote(), 1000.0)
        assert state.get_frame_snapshot() is None


class TestFallback:
    def test_release_on_disconnect_falls_back_on_the_next_local_frame(self):
        clock = _Clock()
        state, router = _router(clock)
        router.select_remote("s1")
        router.remote_frame("s1", _remote(9), 1000.0)

        router.release_remote("s1")

        assert router.source == "local"
        assert router.local_frame(_local(4), 1000.04)
        frame, _, ts = state.get_frame_snapshot()
        assert int(frame[0, 0, 0]) == 4 and ts == 1000.04
        assert state.frame_intrinsics() is None

    def test_a_silent_remote_falls_back_after_the_stale_window(self):
        clock = _Clock()
        state, router = _router(clock, stale=0.5)
        router.select_remote("s1")
        router.remote_frame("s1", _remote(9), 1000.0)

        clock.now += 0.4
        assert not router.local_frame(_local(4), 1000.4)
        clock.now += 0.2
        assert router.local_frame(_local(5), 1000.6)
        assert router.source == "local"

    def test_remote_resumes_when_its_frames_return(self):
        clock = _Clock()
        state, router = _router(clock, stale=0.5)
        router.select_remote("s1")
        router.remote_frame("s1", _remote(9), 1000.0)
        clock.now += 1.0
        router.local_frame(_local(4), 1001.0)

        assert router.remote_frame("s1", _remote(8), 1001.1)
        assert router.source == "remote"

    def test_releasing_someone_elses_stream_changes_nothing(self):
        state, router = _router()
        router.select_remote("s1")
        router.remote_frame("s1", _remote(9), 1000.0)

        router.release_remote("s2")

        assert router.source == "remote"


class TestNoFlicker:
    """Live 2026-10-03: a background browser tab throttled the remote camera
    to ~1 frame/s, and the image flipped between the two cameras every second
    (196 switches).  A remote takes over only once it delivers steadily."""

    def test_a_sparse_remote_never_takes_over(self):
        clock = _Clock()
        state, router = _router(clock, stale=0.5, steady=5)
        router.select_remote("s1")
        for i in range(6):
            clock.now += 1.0
            assert not router.remote_frame("s1", _remote(9), 1000.0 + i)
            assert router.local_frame(_local(4), 1000.0 + i)
        assert router.source == "local"
        assert int(state.get_frame_snapshot()[0][0, 0, 0]) == 4

    def test_a_steady_remote_takes_over_on_its_fifth_frame(self):
        clock = _Clock()
        state, router = _router(clock, stale=0.5, steady=5)
        router.select_remote("s1")
        published = []
        for i in range(5):
            clock.now += 0.04
            published.append(router.remote_frame("s1", _remote(9), 1000.0 + i))
        assert published == [False, False, False, False, True]
        assert router.source == "remote"

    def test_after_a_fallback_one_late_frame_does_not_flip_back(self):
        clock = _Clock()
        state, router = _router(clock, stale=0.5, steady=5)
        router.select_remote("s1")
        for _ in range(5):
            clock.now += 0.04
            router.remote_frame("s1", _remote(9), 1000.0)
        clock.now += 1.0
        assert router.local_frame(_local(4), 1001.0)   # fell back

        clock.now += 0.04
        assert not router.remote_frame("s1", _remote(9), 1001.1)
        assert router.source == "local"


class TestCanonicalFrame:
    def test_wide_frames_are_center_cropped_to_the_canonical_aspect(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[:, 160:1120] = 255          # the central 4:3 region

        out = normalize_frame(frame, 640, 480)

        assert out.shape == (480, 640, 3) and out.dtype == np.uint8
        assert out.min() == 255

    def test_canonical_frames_pass_through_without_a_copy(self):
        frame = _local()
        assert normalize_frame(frame, 640, 480) is frame

    def test_intrinsics_follow_the_horizontal_field_of_view(self):
        fx, fy, cx, cy = estimate_intrinsics(640, 480, 90.0)
        assert fx == pytest.approx(320.0) and fy == fx
        assert (cx, cy) == (320.0, 240.0)
        assert estimate_intrinsics(640, 480, 70.0)[0] == pytest.approx(
            320.0 / math.tan(math.radians(35.0)))


class TestLocalPriority:
    def test_local_camera_wins_then_remote_falls_back_and_local_recovers(self):
        clock = _Clock()
        state = SharedState()
        router = CameraRouter(state, width=640, height=480, remote_hfov_deg=70,
                              steady_frames=2, clock=clock, prefer_local=True)
        router.select_remote('mobile')
        assert router.local_frame(_local(4), 1000)
        assert not router.remote_frame('mobile', _remote(9), 1000)
        clock.now += 0.1
        assert not router.remote_frame('mobile', _remote(9), 1000.1)
        assert router.source == 'local'
        assert int(state.get_frame_snapshot()[0][0, 0, 0]) == 4
        clock.now += 0.45
        assert router.remote_frame('mobile', _remote(9), 1000.55)
        assert router.source == 'remote'
        assert state.frame_intrinsics() is not None
        assert router.local_frame(_local(5), 1000.6)
        assert router.source == 'local'
        assert state.frame_intrinsics() is None
        assert int(state.get_frame_snapshot()[0][0, 0, 0]) == 5
        assert not router.remote_frame('mobile', _remote(9), 1000.6)

    def test_remote_is_usable_without_any_local_camera(self):
        state = SharedState()
        router = CameraRouter(state, width=640, height=480, remote_hfov_deg=70,
                              steady_frames=1, prefer_local=True)
        router.select_remote('mobile')
        assert router.remote_frame('mobile', _remote(), 1000)
        assert router.source == 'remote'
        assert not router.remote_frame('other', _remote(), 1000)


def test_explicit_device_camera_overrides_local_priority_then_releases():
    clock = _Clock()
    state = SharedState()
    router = CameraRouter(state, width=640, height=480, remote_hfov_deg=70,
                          steady_frames=2, clock=clock, prefer_local=True)
    assert router.local_frame(_local(4), 1000)
    router.select_remote("device", prefer_remote=True)
    assert not router.remote_frame("device", _remote(9), 1000.01)
    assert router.remote_frame("device", _remote(9), 1000.02)
    assert not router.local_frame(_local(5), 1000.03)
    assert router.source == "remote"
    assert int(state.get_frame_snapshot()[0][0, 0, 0]) == 9

    clock.now += 0.6
    assert router.local_frame(_local(6), 1000.6)
    assert router.source == "local"
    assert not router.remote_frame("device", _remote(9), 1000.61)
    assert router.remote_frame("device", _remote(9), 1000.62)
    router.release_remote("device")
    assert router.local_frame(_local(7), 1000.63)
    router.select_remote("next")
    assert not router.remote_frame("next", _remote(9), 1000.64)
    assert not router.remote_frame("next", _remote(9), 1000.65)
    assert router.source == "local"


@pytest.mark.parametrize('source', ['local', 'device'])
def test_explicit_source_never_falls_back_or_swaps_on_gaps(source):
    clock = _Clock()
    state = SharedState()
    router = CameraRouter(state, width=640, height=480, remote_hfov_deg=70,
                          steady_frames=5, clock=clock, prefer_local=True)
    router.local_frame(_local(4), 1000)
    router.select_remote('owner', camera_source=source)
    assert state.get_frame_snapshot() is None
    for gap in (0.01, 0.8, 2, 0.1, 1):
        clock.now += gap
        if source == 'device':
            assert not router.local_frame(_local(4), 1000 + clock.now)
            assert router.remote_frame('owner', _remote(9), 1000 + clock.now)
            assert router.source == 'remote'
            assert int(state.get_frame_snapshot()[0][0, 0, 0]) == 9
        else:
            assert not router.remote_frame('owner', _remote(9), 1000 + clock.now)
            assert router.local_frame(_local(4), 1000 + clock.now)
            assert router.source == 'local'
            assert int(state.get_frame_snapshot()[0][0, 0, 0]) == 4
    router.release_remote('owner')
    assert router.local_frame(_local(4), 2000)
    assert router.source == 'local'

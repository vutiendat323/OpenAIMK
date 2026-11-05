"""Presence is safe to run in production: right camera, no stale bodies, no crash.

YOLO + Metric3D only add presence evidence.  These tests pin the three ways it
could mislead the kiosk or take Vision down: depth scaled with another camera's
focal length after a switch, bodies from a camera the Scene has forgotten, and
a Metric3D that cannot load stopping the whole service.
"""

import sys
import threading
import time
import types

import numpy as np

from tests.application.test_pipeline import BODY_M, _cfg, _Depth, _People
from Visual.application.measure_presence import _presence_loop
from Visual.application.state import SharedState

REMOTE = (500.0, 500.0, 320.0, 240.0)


def _run(state, cfg, depth, until, timeout=3.0):
    worker = threading.Thread(target=_presence_loop, args=(state, cfg, depth, _People()),
                              daemon=True)
    worker.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not until():
        time.sleep(0.01)
    state.running = False
    worker.join(timeout=2.0)


class _RecordingDepth(_Depth):
    """Remembers which frame (by its pixel value) came with which intrinsics."""

    def __init__(self):
        self.seen = []

    def estimate(self, rgb, intrinsics, scale):
        self.seen.append((int(rgb[0, 0, 0]), tuple(intrinsics)))
        return super().estimate(rgb, intrinsics, scale)


class _SwitchMidTick(SharedState):
    """The remote camera takes over right after the local frame was read."""

    def __init__(self):
        super().__init__()
        self.switched = False

    def frame_intrinsics(self):
        if not self.switched:
            self.switched = True
            self.put_frame(np.full((480, 640, 3), 7, np.uint8), intrinsics=REMOTE,
                           source="remote")
        return super().frame_intrinsics()


def test_depth_is_scaled_with_the_intrinsics_of_its_own_frame():
    cfg = _cfg()
    state = _SwitchMidTick()
    state.put_frame(np.zeros((480, 640, 3), np.uint8))  # local C920 frame
    depth = _RecordingDepth()

    _run(state, cfg, depth, until=lambda: len(depth.seen) >= 3)

    expected = {0: tuple(cfg.intrinsics), 7: REMOTE}
    assert depth.seen, "presence never ran"
    assert all(intrinsics == expected[value] for value, intrinsics in depth.seen), depth.seen


def test_bodies_from_before_a_camera_switch_never_reach_the_scene():
    cfg = _cfg()
    state = SharedState()
    state.put_frame(np.zeros((480, 640, 3), np.uint8))

    class _SwitchDuringInference(_Depth):
        calls = 0

        def estimate(self, rgb, intrinsics, scale):
            _SwitchDuringInference.calls += 1
            state.scene.reset()  # the track loop saw a new camera meanwhile
            return super().estimate(rgb, intrinsics, scale)

    _run(state, cfg, _SwitchDuringInference(),
         until=lambda: _SwitchDuringInference.calls >= 3)

    assert _SwitchDuringInference.calls >= 3
    assert state.scene.snapshot().body_m == -1.0


def test_the_snapshot_carries_the_frame_with_its_camera():
    state = SharedState()
    frame = np.full((480, 640, 3), 3, np.uint8)
    state.put_frame(frame, timestamp=12.5, intrinsics=REMOTE, source="remote")

    snap = state.frame_snapshot()

    assert snap.frame is not None and int(snap.frame[0, 0, 0]) == 3
    assert (snap.timestamp, snap.intrinsics, snap.source) == (12.5, REMOTE, "remote")


def test_a_presence_tick_still_reports_bodies_when_nothing_switches():
    cfg = _cfg()
    state = SharedState()
    state.put_frame(np.zeros((480, 640, 3), np.uint8))

    _run(state, cfg, _Depth(), until=lambda: state.scene.snapshot().body_m > 0)

    assert state.scene.snapshot().body_m == BODY_M


_METRIC3D = "Visual.infrastructure.depth.metric3d"


def _depth_cfg():
    cfg = _cfg()
    cfg.metric3d_variant, cfg.metric3d_half, cfg.metric3d_input_size = "vit_small", True, (308, 532)
    return cfg


def _fake_metric3d(monkeypatch, estimator):
    module = types.ModuleType(_METRIC3D)
    module.DepthEstimator = estimator
    monkeypatch.setitem(sys.modules, _METRIC3D, module)


def test_metric3d_that_cannot_be_imported_leaves_vision_running(monkeypatch, caplog):
    import Visual.main as service

    monkeypatch.setitem(sys.modules, _METRIC3D, None)  # e.g. ../Metric3D missing

    assert service._build_depth(_depth_cfg()) is None
    assert "depth estimator" in caplog.text


def test_metric3d_that_fails_to_load_leaves_vision_running(monkeypatch, caplog):
    import Visual.main as service

    class _OutOfMemory:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("CUDA out of memory")

    _fake_metric3d(monkeypatch, _OutOfMemory)

    assert service._build_depth(_depth_cfg()) is None
    assert "CUDA out of memory" in caplog.text


def test_metric3d_that_loads_reports_ready(monkeypatch, capsys):
    import Visual.main as service

    class _Loaded:
        def __init__(self, variant, device, use_half=False, input_size=None):
            self.args = (variant, device, use_half, input_size)

    _fake_metric3d(monkeypatch, _Loaded)

    depth = service._build_depth(_depth_cfg())

    assert isinstance(depth, _Loaded) and depth.args == ("vit_small", "cpu", True, (308, 532))
    assert "[main] depth estimator ready" in capsys.readouterr().out

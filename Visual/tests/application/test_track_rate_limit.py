"""P1: the track loop must respect cfg.track_max_fps.

Uncapped it ran ~150 fps and pinned a full core. These drive _track_loop
with fakes so no camera, ONNX session or GPU is needed.
"""

import time

import pytest

from Visual.application.state import SharedState
from Visual.application.track_faces import _track_loop


class _Cfg:
    """Minimal stand-in for Config — only what _track_loop reads."""

    track_buffer = 15
    track_thresh = 0.5
    match_thresh = 0.3
    match_thresh_second = 0.5
    track_init_thresh = 0.7
    reid_weight = 0.0
    gallery_size = 5
    embedder_model_path = "/nonexistent-so-reid-is-skipped.onnx"
    embedder_device = "cpu"
    camera_fx = camera_fy = 633.3   # face-distance PnP needs intrinsics
    camera_cx, camera_cy = 320.0, 240.0
    face_ipd_m = 0.063

    def __init__(self, fps):
        self.track_max_fps = fps


class _Detector:
    def __init__(self):
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        return []


def _run(fps, seconds):
    import numpy as np

    state = SharedState()
    state.put_frame(np.zeros((8, 8, 3), dtype=np.uint8))
    det = _Detector()

    import threading

    from Visual.infrastructure.faces.bytetrack import ByteTrack

    cfg = _Cfg(fps)
    tracker = ByteTrack(cfg.track_buffer, cfg.track_thresh, cfg.match_thresh,
                        cfg.match_thresh_second, cfg.track_init_thresh)
    t = threading.Thread(
        target=_track_loop, args=(state, cfg, det, tracker), daemon=True
    )
    t.start()
    time.sleep(seconds)
    state.running = False
    t.join(timeout=2.0)
    return det.calls


def test_cap_limits_detect_rate():
    calls = _run(fps=10.0, seconds=1.0)
    # 10 fps over ~1s: allow generous slack for scheduler jitter, but it
    # must be nowhere near the uncapped hundreds.
    assert 3 <= calls <= 20, calls


def test_zero_disables_cap():
    capped = _run(fps=5.0, seconds=0.5)
    uncapped = _run(fps=0, seconds=0.5)
    assert uncapped > capped * 3, (uncapped, capped)

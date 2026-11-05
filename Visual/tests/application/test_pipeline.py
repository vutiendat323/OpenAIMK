"""The whole pipeline in-process: real loops, real tracker, real Scene and
server, with stand-in models.  No camera, no GPU, no weights.

A face is projected from the same generic model PnP solves against, so the
face distance is known exactly; a stand-in depth map puts the body at 1.4 m.
"""

import time
from types import SimpleNamespace

import numpy as np
import pytest

from Visual.domain.faces import FaceDetection
from Visual.infrastructure.faces.bytetrack import ByteTrack
from Visual.main import start_workers
from Visual.application.state import SharedState
from Visual.presentation.ws_server import VisionWSServer
from Visual.domain.geometry import _FACE_MODEL

FX = 612.0
K = np.array([[FX, 0, 320.0], [0, FX, 240.0], [0, 0, 1.0]])
FACE_M, BODY_M = 1.2, 1.4


def _face_at(z, dx=0.0):
    pts = (_FACE_MODEL + [dx, -0.03, z]) @ K.T
    kps = [(float(x / w), float(y / w)) for x, y, w in pts]
    xs, ys = [p[0] for p in kps], [p[1] for p in kps]
    box = (min(xs) - 15, min(ys) - 25, max(xs) + 15, max(ys) + 15)
    return FaceDetection(bbox=box, confidence=0.95, landmarks=kps)


class _Faces:
    def detect(self, frame):
        return [_face_at(FACE_M)]


class _Depth:
    def estimate(self, rgb, intrinsics, scale):
        depth = np.full(rgb.shape[:2], 4.0, dtype=np.float32)
        depth[100:480, 200:440] = BODY_M
        return depth


class _People:
    def detect(self, frame):
        return [(200.0, 100.0, 440.0, 480.0, 0.9)]


class _Lips:
    """Opens and closes the mouth every frame, like speech."""

    def __init__(self):
        self.calls = 0

    def opening(self, frame, box):
        self.calls += 1
        return 0.3 if self.calls % 2 else 0.0


class _Spoof:
    def check_faces(self, frame, boxes):
        return {i: (False, 0.04) for i in range(len(boxes))}


def _cfg():
    return SimpleNamespace(
        track_max_fps=30.0, camera_fx=FX, camera_fy=FX, camera_cx=320.0, camera_cy=240.0,
        face_ipd_m=0.063, device="cpu", intrinsics=(FX, FX, 320.0, 240.0),
        canonical_to_real_scale=FX / 1000.0, person_shrink=0.5, person_depth_percentile=20.0,
        depth_interval_sec=0.05, spoof_interval_sec=0.05, distance_threshold=1.0,
        asd_provider="none", asd_audio_offset_secs=0.0,
    )


@pytest.fixture
def running_pipeline():
    state = SharedState()
    state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8))
    models = {"face_detector": _Faces(), "tracker": ByteTrack(15, 0.5, 0.3, 0.5, 0.7),
              "embedder": None, "spoof_detector": _Spoof(),
              "depth_estimator": _Depth(), "person_detector": _People(),
              "lip_reader": _Lips()}
    threads = start_workers(state, _cfg(), models)
    yield state
    state.running = False
    for t in threads:
        t.join(timeout=2.0)


def _wait_for(state, ready, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        snap = state.scene.snapshot()
        if ready(snap):
            return snap
        time.sleep(0.02)
    pytest.fail(f"pipeline never became ready: {state.scene.snapshot()}")


def test_face_and_body_reach_the_kiosk_event(running_pipeline):
    _wait_for(running_pipeline, lambda s: s.nearest and s.nearest.dist > 0 and s.body_m > 0)
    event = VisionWSServer(running_pipeline, port=0)._build_event()
    assert event["event"] == "person_near"
    assert event["nearest_m"] == pytest.approx(FACE_M, abs=0.02)
    assert event["body_m"] == pytest.approx(BODY_M, abs=0.01)
    assert event["facing"] is True


def test_the_face_is_attached_to_its_body_and_tagged_live(running_pipeline):
    snap = _wait_for(running_pipeline,
                     lambda s: s.nearest and s.nearest.body_m and s.nearest.spoof is not None)
    assert snap.nearest.body_m == pytest.approx(BODY_M, abs=0.01)
    assert snap.nearest.spoof_flag is False and snap.nearest.gate is True


def test_a_talking_mouth_reaches_the_scene(running_pipeline):
    snap = _wait_for(running_pipeline, lambda s: s.nearest and s.nearest.mouth is not None)
    snap = _wait_for(running_pipeline, lambda s: s.nearest.mouth is not None and s.nearest.mouth > 0.5)
    assert snap.nearest.mouth <= 1.0


def _wait_until(predicate, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail("condition never became true")


def test_no_asd_crops_offered_while_no_stream_is_active(running_pipeline):
    # The fixture never starts an ASD stream: the tracker must never reach
    # into state.asd at all.
    _wait_for(running_pipeline, lambda s: s.nearest and s.nearest.dist > 0)
    time.sleep(0.1)
    assert running_pipeline.asd._crops == []


def test_nearest_confirmed_track_is_selected_and_offered_once_per_frame(running_pipeline):
    # The fixture's frame never changes after start_workers, so frame_seq is
    # constant for the whole test: any crop count above 1 would mean the
    # tracker re-offered the same frame sequence instead of gating on it.
    state = running_pipeline
    state.asd.start_stream("s1")
    _wait_until(lambda: state.asd._track_id is not None)
    time.sleep(0.2)  # several more track-loop passes at the same frame_seq
    assert len(state.asd._crops) == 1
    assert state.asd._crops[0][1].shape == (112, 112)


class _TwoFaces:
    """Two well-separated faces at different distances, both confirmed
    every pass."""

    def detect(self, frame):
        return [_face_at(1.0, dx=0.4), _face_at(2.5, dx=-0.4)]


class _ToggleableFace:
    """One face, confirmed every pass until ``miss`` is set."""

    def __init__(self):
        self.miss = False

    def detect(self, frame):
        return [] if self.miss else [_face_at(FACE_M)]


def _start_track_only(state, face_detector):
    models = {"face_detector": face_detector, "tracker": ByteTrack(15, 0.5, 0.3, 0.5, 0.7),
              "embedder": None, "spoof_detector": None,
              "depth_estimator": None, "person_detector": None, "lip_reader": None}
    return start_workers(state, _cfg(), models)


@pytest.fixture
def two_faces_pipeline():
    state = SharedState()
    state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8))
    threads = _start_track_only(state, _TwoFaces())
    yield state
    state.running = False
    for t in threads:
        t.join(timeout=2.0)


@pytest.fixture
def toggleable_face_pipeline():
    state = SharedState()
    state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8))
    detector = _ToggleableFace()
    threads = _start_track_only(state, detector)
    yield state, detector
    state.running = False
    for t in threads:
        t.join(timeout=2.0)


def test_asd_selects_the_nearer_of_two_confirmed_tracks(two_faces_pipeline):
    state = two_faces_pipeline
    snap = _wait_for(state, lambda s: len([p for p in s.people if p.raw is not None]) >= 2)
    nearer_id = min((p for p in snap.people if p.raw is not None), key=lambda p: p.raw).id

    state.asd.start_stream("s1")
    _wait_until(lambda: state.asd._track_id is not None)
    assert state.asd._track_id == nearer_id


def test_coasting_track_is_deselected_and_offers_no_crop(toggleable_face_pipeline):
    state, detector = toggleable_face_pipeline
    state.asd.start_stream("s1")
    # select_track and push_crop happen in the same tracker pass, in that
    # order: wait for the crop itself, not just the track id, or this can
    # observe a selected-but-not-yet-offered moment and flake.
    _wait_until(lambda: len(state.asd._crops) >= 1)

    detector.miss = True  # the track now coasts, then goes unconfirmed
    for _ in range(10):
        state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8))
        time.sleep(0.02)
    _wait_until(lambda: state.asd._track_id is None)
    assert state.asd._crops == []


def test_asd_crop_error_is_logged_and_does_not_kill_the_track_thread(running_pipeline, monkeypatch):
    import Visual.application.track_faces as track_faces_module

    def _boom(frame, box):
        raise ValueError("bad crop")

    monkeypatch.setattr(track_faces_module, "prepare_face_crop", _boom)
    state = running_pipeline
    state.asd.start_stream("s1")
    _wait_for(state, lambda s: s.nearest and s.nearest.dist > 0)
    before = state.timings()["track"]
    time.sleep(0.2)
    # The track thread must still be alive and looping: timings keep
    # advancing and no crop was ever offered (the crop call always raises).
    assert state.timings()["track"] != before
    assert state.asd._crops == []


# ---------------------------------------------------------------------------
# Active-speaker provider: optional, and never able to take tracking down.
# ---------------------------------------------------------------------------

import sys

from Visual.main import _build_active_speaker

_LIGHT_ASD = "Visual.infrastructure.active_speaker.light_asd"


def test_disabled_provider_is_never_imported_and_reports_disabled(monkeypatch):
    monkeypatch.delitem(sys.modules, _LIGHT_ASD, raising=False)
    cfg = _cfg()
    assert _build_active_speaker(cfg) is None
    assert _LIGHT_ASD not in sys.modules
    state = SharedState()
    threads = _start_track_only(state, _Faces())
    try:
        assert state.asd_status == "disabled"
        assert "asd" not in [t.name for t in threads]
    finally:
        state.running = False
        for t in threads:
            t.join(timeout=2.0)


def test_missing_model_reports_unavailable_and_starts_no_worker(tmp_path):
    cfg = _cfg()
    cfg.asd_provider = "light_asd"
    cfg.asd_model_path = str(tmp_path / "missing.onnx")
    assert _build_active_speaker(cfg) is None
    state = SharedState()
    models = {"face_detector": _Faces(), "tracker": ByteTrack(15, 0.5, 0.3, 0.5, 0.7),
              "embedder": None, "spoof_detector": None, "depth_estimator": None,
              "person_detector": None, "lip_reader": None, "active_speaker": None}
    threads = start_workers(state, cfg, models)
    try:
        assert state.asd_status == "unavailable"
        assert "asd" not in [t.name for t in threads]
    finally:
        state.running = False
        for t in threads:
            t.join(timeout=2.0)


class _BrokenAsd:
    def __init__(self):
        self.calls = 0

    def predict(self, pcm16, crops):
        self.calls += 1
        raise RuntimeError("CUDA fell over")


def test_asd_model_exception_does_not_kill_face_tracking_or_mouths(capsys):
    state = SharedState()
    state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8))
    lips, asd = _Lips(), _BrokenAsd()
    models = {"face_detector": _Faces(), "tracker": ByteTrack(15, 0.5, 0.3, 0.5, 0.7),
              "embedder": None, "spoof_detector": None, "depth_estimator": None,
              "person_detector": None, "lip_reader": lips, "active_speaker": asd}
    cfg = _cfg()
    cfg.asd_provider = "light_asd"
    threads = {t.name: t for t in start_workers(state, cfg, models)}
    try:
        assert state.asd_status == "ready"
        state.asd.start_stream("s1")
        audio_t0 = time.time() - 1.1
        for i in range(13):
            state.asd.push_audio("s1", i, audio_t0 - 0.04 + 0.08 * i,
                                 np.zeros(1280, dtype=np.int16))
        # One camera frame per window bin, each offered to ASD by the tracker.
        # Wait on each frame's own crop, not a count: the fixture frame's crop
        # (stamped "now") may land late and be dropped as a backward step.
        for k in range(25):
            ts = audio_t0 + 0.02 + 0.04 * k
            state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8), timestamp=ts)
            _wait_until(lambda: (state.asd._crops and state.asd._crops[-1][0] == ts)
                        or state.asd_status != "ready")
            if state.asd_status != "ready":
                break

        _wait_until(lambda: state.asd_status == "unavailable")
        threads["asd"].join(timeout=2.0)
        assert asd.calls == 1 and not threads["asd"].is_alive()
        assert not state.asd.active
        assert "[asd]" in capsys.readouterr().out

        before = lips.calls
        state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8))
        _wait_until(lambda: lips.calls > before)
        assert threads["track"].is_alive()
    finally:
        state.running = False
        for t in threads.values():
            t.join(timeout=2.0)


def test_pinned_track_is_kept_even_when_another_face_is_nearer(two_faces_pipeline):
    state = two_faces_pipeline
    snap = _wait_for(state, lambda s: len([p for p in s.people if p.raw is not None]) >= 2)
    farther_id = max((p for p in snap.people if p.raw is not None), key=lambda p: p.raw).id

    state.asd.start_stream("s1")
    state.asd.pin_track(farther_id)
    # ASD selection runs once per new camera frame: feed a few.
    for _ in range(5):
        state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8))
        time.sleep(0.03)
    _wait_until(lambda: len(state.asd._crops) >= 2)
    assert state.asd._track_id == farther_id


def test_hidden_pinned_track_is_never_replaced(toggleable_face_pipeline):
    state, detector = toggleable_face_pipeline
    state.asd.start_stream("s1")
    _wait_until(lambda: len(state.asd._crops) >= 1)
    pinned = state.asd._track_id
    state.asd.pin_track(pinned)
    crops_before = len(state.asd._crops)

    detector.miss = True
    for _ in range(10):
        state.put_frame(np.zeros((480, 640, 3), dtype=np.uint8))
        time.sleep(0.02)
    time.sleep(0.2)
    assert state.asd._track_id == pinned
    assert len(state.asd._crops) <= crops_before + 1

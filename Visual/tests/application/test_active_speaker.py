"""prepare_face_crop: matches the upstream Columbia_test.py crop geometry.

The reference below is an independent re-implementation of
Columbia_test.py:173-181 (crop_video) and :205-213 (evaluate_network) using
numpy.pad directly, rather than calling into our own cv2-based
implementation -- so a slicing/ordering bug in ours would still show up here.
"""

import cv2
import numpy as np
import pytest

from Visual.application.active_speaker import prepare_face_crop


def _reference_crop(frame_bgr: np.ndarray, box: tuple, cs: float = 0.40) -> np.ndarray:
    x1, y1, x2, y2 = box
    bs = max(x2 - x1, y2 - y1) / 2.0
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    bsi = int(bs * (1 + 2 * cs))
    padded = np.pad(frame_bgr, ((bsi, bsi), (bsi, bsi), (0, 0)),
                    "constant", constant_values=(110, 110))
    my, mx = cy + bsi, cx + bsi
    face = padded[int(my - bs):int(my + bs * (1 + 2 * cs)),
                  int(mx - bs * (1 + cs)):int(mx + bs * (1 + cs))]
    # evaluate_network: grayscale, THEN resize (a no-op there, since
    # crop_video already wrote 224x224 frames), then center-crop 112x112.
    # Reproduced here as resize-then-grayscale, which is what actually ran:
    # crop_video's cv2.resize(face, (224, 224)) is what shaped the stored
    # frame; evaluate_network's later resize to the same size is a no-op.
    face = cv2.resize(face, (224, 224))
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    return gray[56:168, 56:168]


def _random_frame(h=240, w=320, seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


class TestPrepareFaceCrop:
    def test_matches_upstream_formula_for_an_interior_box(self):
        frame = _random_frame()
        box = (120.0, 80.0, 200.0, 180.0)
        out = prepare_face_crop(frame, box)
        assert out is not None
        assert out.shape == (112, 112)
        assert out.dtype == np.uint8
        np.testing.assert_array_equal(out, _reference_crop(frame, box))

    def test_matches_upstream_formula_for_a_box_near_the_edge(self):
        # Close enough to the top-left corner that the crop region extends
        # past the real frame -- the 110 padding must show up here.
        frame = _random_frame()
        box = (5.0, 5.0, 55.0, 65.0)
        out = prepare_face_crop(frame, box)
        assert out is not None
        assert out.shape == (112, 112)
        np.testing.assert_array_equal(out, _reference_crop(frame, box))

    def test_degenerate_box_returns_none(self):
        frame = _random_frame()
        assert prepare_face_crop(frame, (50.0, 50.0, 50.0, 90.0)) is None  # zero width
        assert prepare_face_crop(frame, (50.0, 90.0, 90.0, 50.0)) is None  # inverted

    def test_far_out_of_bounds_box_returns_none(self):
        # A small box centered well outside the frame: the fixed padding
        # around it never reaches back to real pixels.
        frame = _random_frame()
        assert prepare_face_crop(frame, (5000.0, 5000.0, 5040.0, 5040.0)) is None


# ---------------------------------------------------------------------------
# _asd_loop: take -> infer (outside the buffer lock) -> publish, one at a time.
# ---------------------------------------------------------------------------

import threading
import time
from types import SimpleNamespace

from Visual.application.active_speaker import _asd_loop
from Visual.application.state import SharedState

_PROBS = np.full(25, 0.8, dtype=np.float32)


def _feed_window(asd, stream_id="s1", track_id=7, audio_t0=100.0):
    """13 contiguous packets ending at audio_t0 + 1.0 and 25 matching crops."""
    first = audio_t0 - 0.04
    for i in range(13):
        asd.push_audio(stream_id, i, first + i * 0.08, np.full(1280, i, dtype=np.int16))
    asd.select_track(track_id)
    for k in range(25):
        asd.push_crop(track_id, audio_t0 + 0.02 + 0.04 * k, np.full((112, 112), k, np.uint8))


class _Detector:
    def __init__(self, probs=_PROBS, block=False, error=None):
        self.probs, self.error = probs, error
        self.entered = threading.Event()
        self.release = threading.Event()
        if not block:
            self.release.set()
        self.calls = 0

    def predict(self, pcm16, crops):
        self.calls += 1
        self.entered.set()
        self.release.wait(5.0)
        if self.error is not None:
            raise self.error
        return self.probs


def _wait(predicate, seconds=3.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _run(state, detector):
    state.asd_status = "ready"
    cfg = SimpleNamespace(asd_audio_offset_secs=0.0)
    t = threading.Thread(target=_asd_loop, args=(state, cfg, detector), daemon=True)
    t.start()
    return t


def _stop(state, thread):
    state.running = False
    thread.join(timeout=2.0)


def _fresh_state():
    state = SharedState()
    state.asd.start_stream("s1")
    _feed_window(state.asd, audio_t0=time.time() - 1.1)
    return state


class TestAsdLoop:
    def test_publishes_the_detectors_probabilities_for_the_issued_window(self):
        state = _fresh_state()
        detector = _Detector()
        thread = _run(state, detector)
        try:
            assert _wait(lambda: state.asd.latest_result(time.time()) is not None)
            result = state.asd.latest_result(time.time())
            assert result.stream_id == "s1" and result.track_id == 7
            np.testing.assert_array_equal(result.probabilities, _PROBS)
            assert detector.calls == 1  # the same audio end is never re-run
        finally:
            _stop(state, thread)

    @pytest.mark.parametrize("reset", [
        lambda asd: asd.stop_stream("s1"),     # disconnect / stop
        lambda asd: asd.select_track(8),       # nearest track switched
    ])
    def test_late_result_after_a_reset_is_not_published(self, reset):
        state = _fresh_state()
        detector = _Detector(block=True)
        thread = _run(state, detector)
        try:
            assert detector.entered.wait(2.0)
            reset(state.asd)
            detector.release.set()
            time.sleep(0.2)
            assert state.asd.latest_result(time.time()) is None
            assert thread.is_alive()
        finally:
            _stop(state, thread)

    def test_never_takes_another_window_while_one_is_in_flight(self, monkeypatch):
        state = _fresh_state()
        takes = []
        real_next = state.asd.next_window
        monkeypatch.setattr(state.asd, "next_window",
                            lambda **kw: takes.append(1) or real_next(**kw))
        detector = _Detector(block=True)
        thread = _run(state, detector)
        try:
            assert detector.entered.wait(2.0)
            before = len(takes)
            time.sleep(0.3)  # several 80 ms hops
            assert len(takes) == before
        finally:
            detector.release.set()
            _stop(state, thread)

    @pytest.mark.parametrize("detector", [
        _Detector(error=RuntimeError("onnx exploded")),
        _Detector(probs=np.full(24, 0.8, np.float32)),          # wrong length
        _Detector(probs=np.full(25, np.nan, np.float32)),       # non-finite
    ])
    def test_model_failure_disables_asd_for_the_process(self, detector, capsys):
        state = _fresh_state()
        thread = _run(state, detector)
        try:
            thread.join(timeout=2.0)
            assert not thread.is_alive()
            assert state.asd_status == "unavailable"
            assert not state.asd.active  # stream stopped: its scores are gone
            assert state.asd.latest_result(time.time()) is None
            assert capsys.readouterr().out.count("[asd]") == 1
        finally:
            _stop(state, thread)


class TestAsdLoopWakeUp:
    def test_the_worker_waits_on_input_not_a_fixed_sleep(self, monkeypatch):
        state = _fresh_state()
        waits = []
        real_wait = state.asd.wait_for_input

        def spy(timeout):
            waits.append(timeout)
            real_wait(timeout)

        monkeypatch.setattr(state.asd, "wait_for_input", spy)
        detector = _Detector()
        thread = _run(state, detector)
        try:
            assert _wait(lambda: state.asd.latest_result(time.time()) is not None)
        finally:
            _stop(state, thread)
        assert waits and all(w == pytest.approx(0.08) for w in waits)

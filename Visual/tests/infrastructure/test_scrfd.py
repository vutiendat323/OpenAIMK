"""Unit tests for SCRFDFaceDetector — SCRFD ONNX face detection wrapper."""

import numpy as np
import pytest

# Tests must be run from within AI/ directory (app convention)
from Visual.infrastructure.faces.scrfd import SCRFDFaceDetector
from Visual.domain.faces import FaceDetection
from Visual.config import Config


@pytest.fixture
def detector():
    cfg = Config()
    return SCRFDFaceDetector(
        model_path=cfg.scrfd_model,
        conf_thresh=cfg.scrfd_conf,
        nms_thresh=cfg.scrfd_nms,
        input_size=cfg.scrfd_input_size,
        device="cpu",
    )


class TestFaceDetector:
    def test_load_model_succeeds(self, detector):
        assert detector._session is not None
        assert len(detector._output_names) == 9  # 3 strides x 3 heads
        assert len(detector._anchors) == 3

    def test_detect_returns_list(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        assert isinstance(result, list)
        assert len(result) == 0  # black frame has no faces

    def test_detect_handles_non_square_frame(self, detector):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = detector.detect(frame)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_to_tracker_tuple(self):
        fd = FaceDetection(
            bbox=(10.0, 20.0, 100.0, 120.0),
            confidence=0.95,
        )
        tup = fd.to_tracker_tuple()
        assert tup == (10.0, 20.0, 100.0, 120.0, 0.95)

    def test_warmup(self, detector):
        detector.warmup()  # should not raise

    def test_anchors_cover_input_range(self, detector):
        for stride, anchors in zip(detector._strides, detector._anchors):
            w, h = detector._input_size
            assert anchors[:, 0].min() >= 0
            assert anchors[:, 0].max() < w
            assert anchors[:, 1].min() >= 0
            assert anchors[:, 1].max() < h


class TestAnchorGrid:
    """Anchor centres must match SCRFD's training convention (top-left of cell).

    Half-a-cell off shifted boxes and landmarks by stride/2, which is 8-32 px on
    the frame and different per input size, and PnP solved a wrong head pose.
    """

    def test_anchor_grid_starts_at_origin_and_steps_by_stride(self, detector):
        for stride, anchors in zip(detector._strides, detector._anchors):
            xs = np.unique(anchors[:, 0])
            assert xs[0] == 0.0
            assert xs[1] - xs[0] == stride

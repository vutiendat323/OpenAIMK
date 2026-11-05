"""Unit tests for SpoofDetector — MiniFASNet PAD ensemble."""

import numpy as np
import pytest

from Visual.infrastructure.spoof.minifasnet import SpoofDetector


@pytest.fixture
def detector():
    det = SpoofDetector(device="cpu")
    det.prepare()
    return det


class TestSpoofDetector:
    def test_prepare_loads_pad_models(self, detector):
        assert detector.is_prepared
        assert len(detector._pad_models) == 2  # V2 + V1SE
        # No face detector — verify SCRFD is absent
        assert not hasattr(detector, "_face_detector")
        assert not hasattr(detector, "detect_faces")
        assert not hasattr(detector, "_create_face_detector")
        assert not hasattr(detector, "_match_faces_to_person")

    def test_predict_returns_correct_types(self, detector):
        face_crop = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        is_live, live_score, replay_score = detector.predict(face_crop)
        assert isinstance(is_live, bool)
        assert isinstance(live_score, float)
        assert isinstance(replay_score, float)
        assert 0.0 <= live_score <= 1.0
        assert 0.0 <= replay_score <= 1.0

    def test_predict_requires_prepare(self):
        det = SpoofDetector(device="cpu")
        face_crop = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        with pytest.raises(RuntimeError, match="prepare"):
            det.predict(face_crop)

    def test_check_faces_returns_dict(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        face_bboxes = [(100, 80, 200, 180), (300, 200, 400, 320)]
        results = detector.check_faces(frame, face_bboxes)
        assert isinstance(results, dict)
        assert 0 in results
        assert 1 in results
        for is_spoof, conf in results.values():
            assert isinstance(is_spoof, bool)
            assert isinstance(conf, float)

    def test_check_faces_empty_list(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.check_faces(frame, [])
        assert results == {}

    def test_check_faces_too_small_bbox(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.check_faces(frame, [(0, 0, 2, 2)])  # tiny bbox
        assert results[0] == (False, 0.0)

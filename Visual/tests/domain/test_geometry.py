"""Distance geometry: face distance (PnP), body distance, box maths."""

import numpy as np
import pytest

from Visual.domain.geometry import (
    iou_batch, body_distance, box_contains_center,
)


_K = np.array([[633.3, 0.0, 324.4], [0.0, 633.6, 242.4], [0.0, 0.0, 1.0]])


def _face_points(z, yaw_deg=0.0):
    import cv2
    from Visual.domain.geometry import _FACE_MODEL
    rvec = np.array([0.0, np.radians(yaw_deg), 0.0])
    pts, _ = cv2.projectPoints(_FACE_MODEL, rvec, np.array([0.05, -0.02, z]), _K, None)
    return pts.reshape(5, 2)


def test_face_distance_is_exact_under_head_turn():
    """A turned head must not read as farther away (raw eye spacing: +20% at 40 deg)."""
    from Visual.domain.geometry import face_distance
    for z in (0.5, 1.0, 2.0):
        for yaw in (0, 20, 40):
            assert abs(face_distance(_face_points(z, yaw), _K) - z) / z < 0.01, (z, yaw)


def test_face_distance_rejects_landmarks_no_face_fits():
    from Visual.domain.geometry import face_distance
    pts = _face_points(1.0)
    pts[2, 1] += 60.0              # nose below the mouth
    assert face_distance(pts, _K) is None
    assert face_distance(None, _K) is None


def test_face_distance_scales_with_the_ipd_knob():
    from Visual.domain.geometry import face_distance
    z = face_distance(_face_points(1.0), _K, ipd_m=0.066)
    assert abs(z - 66 / 63) < 0.005


class TestBodyDistance:
    """Sampling inside a person box must ignore the background it contains.

    A body box always holds background: between the arms, past the shoulders.
    Taking a median over the whole box let that background in, and a person
    walking sideways read 1.7-2.0 m while standing 1.0 m away.
    """

    def _map(self, person_m: float, background_m: float) -> np.ndarray:
        depth = np.full((100, 100), background_m, dtype=np.float32)
        depth[30:70, 40:60] = person_m          # torso: a narrow strip in the box
        return depth

    def test_background_inside_the_box_does_not_pull_the_reading(self):
        depth = self._map(person_m=1.0, background_m=4.0)
        box = (20, 20, 80, 80)                  # box is 3x wider than the torso
        assert body_distance(depth, box) == pytest.approx(1.0, abs=0.05)
        # what the naive reading would have said, and why this test exists
        assert float(np.median(depth[20:80, 20:80])) > 3.0

    def test_returns_none_when_nothing_valid_is_in_the_box(self):
        depth = np.zeros((100, 100), dtype=np.float32)
        assert body_distance(depth, (20, 20, 80, 80)) is None

    def test_returns_none_for_a_degenerate_box(self):
        assert body_distance(np.ones((10, 10), dtype=np.float32), (5, 5, 5, 5)) is None


class TestBoxContainsCenter:
    def test_face_inside_body_matches(self):
        assert box_contains_center((0, 0, 100, 200), (40, 10, 60, 40)) is True

    def test_face_outside_body_does_not_match(self):
        assert box_contains_center((0, 0, 100, 200), (140, 10, 160, 40)) is False

"""Numerical validation follows exactly the pixels supplied to presentation."""

import numpy as np

from scripts.prepare_ditto_mouth import visible_errors


def test_unpresented_pixels_cannot_change_the_visible_mouth_score():
    expected = np.zeros((512, 512, 3), np.float32)
    actual = expected.copy()
    actual[:200] = 255
    result = visible_errors(actual, expected, [(256, 361, 78, 57)])
    assert result["worst_max_rgb255"] == 0
    assert result["worst_mae_rgb255"] == 0


def test_visible_lip_errors_remain_measured_at_full_opacity():
    expected = np.zeros((512, 512, 3), np.float32)
    actual = expected.copy()
    actual[360:363, 255:258] = 3
    result = visible_errors(actual, expected, [(256, 361, 78, 57)])
    assert result["worst_max_rgb255"] == 3
    assert result["worst_mae_rgb255"] > 0

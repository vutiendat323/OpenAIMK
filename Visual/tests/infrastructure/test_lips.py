"""LipReader: MediaPipe face landmarks -> inner-lip opening ratio."""

import os

import numpy as np
import pytest

from Visual.config import Config

MODEL = Config().lip_model_path
pytestmark = pytest.mark.skipif(not os.path.isfile(MODEL), reason="landmark model missing")


def test_opening_is_a_small_ratio_on_a_blank_face_box():
    from Visual.infrastructure.faces.lips import LipReader

    reader = LipReader(MODEL)
    frame = np.full((480, 640, 3), 128, np.uint8)
    value = reader.opening(frame, (200.0, 150.0, 360.0, 330.0))
    assert value is None or 0.0 <= value < 5.0


def test_box_outside_the_frame_is_still_answered_without_error():
    from Visual.infrastructure.faces.lips import LipReader

    reader = LipReader(MODEL)
    frame = np.zeros((480, 640, 3), np.uint8)
    reader.opening(frame, (600.0, 400.0, 700.0, 520.0))

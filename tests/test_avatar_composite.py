"""Pixel regressions; run with the prepared avatar interpreter (numpy/OpenCV).

.runtime/livetalking-venv/bin/python -m unittest discover -s tests -p test_avatar_composite.py
"""

import unittest

try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest("Requires the prepared avatar environment") from error

from trendcoffee.avatar_composite import composite_face


class FaceCompositeTests(unittest.TestCase):
    def setUp(self):
        self.source = np.full((300, 240, 3), 40, dtype=np.uint8)
        self.prediction = np.full((256, 256, 3), 220, dtype=np.float32)
        self.coords = (30, 250, 40, 200)

    def test_lipsync_preserves_original_eyes_hair_and_background(self):
        result = composite_face(self.source, self.prediction, self.coords)
        np.testing.assert_array_equal(result[:110], self.source[:110])
        np.testing.assert_array_equal(result[:, :40], self.source[:, :40])
        np.testing.assert_array_equal(result[:, 200:], self.source[:, 200:])
        np.testing.assert_array_equal(result[250:], self.source[250:])

    def test_generated_mouth_is_not_diluted_with_closed_source_lips(self):
        result = composite_face(self.source, self.prediction, self.coords)
        self.assertTrue((result[180:210, 90:150] == 220).all())

    def test_face_boundary_is_feathered_without_mutating_cached_frames(self):
        original = self.source.copy()
        result = composite_face(self.source, self.prediction, self.coords)
        # A hard rectangular replacement creates a 180-level edge on both axes.
        self.assertLess(np.abs(np.diff(result.astype(int), axis=0)).max(), 22)
        self.assertLess(np.abs(np.diff(result.astype(int), axis=1)).max(), 22)
        np.testing.assert_array_equal(self.source, original)

    def test_out_of_range_predictions_do_not_wrap_into_dark_pixels(self):
        self.prediction[:] = 260
        result = composite_face(self.source, self.prediction, self.coords)
        self.assertTrue((result[180:210, 90:150] == 255).all())


if __name__ == "__main__":
    unittest.main()

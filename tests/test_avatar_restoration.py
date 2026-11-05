"""Run with the prepared avatar interpreter (OpenCV/NumPy)."""

import unittest

try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest("Requires the prepared avatar environment") from error

from trendcoffee.avatar_restoration import blend_mouth_detail, face_alignment


class MouthDetailTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.full((160, 120, 3), 100, dtype=np.uint8)
        self.points = np.full((68, 2), (60, 105), dtype=np.float32)
        self.points[48], self.points[54] = (40, 100), (80, 100)
        self.points[36:42] = (40, 50)
        self.points[42:48] = (80, 50)
        self.points[30] = (60, 80)

    def test_restoration_cannot_recolor_flat_lips_or_skin(self):
        restored = self.frame.copy()
        restored[:] = (80, 120, 180)
        result = blend_mouth_detail(self.frame, restored, self.points)
        np.testing.assert_array_equal(result, self.frame)

    def test_only_mouth_detail_changes_eyes_background_and_input_stay_intact(self):
        restored = self.frame.copy()
        restored[98:110:2, 45:75] = 220
        before = self.frame.copy()
        result = blend_mouth_detail(self.frame, restored, self.points)
        self.assertGreater(np.abs(result[90:120].astype(int) - 100).max(), 20)
        np.testing.assert_array_equal(result[:75], self.frame[:75])
        np.testing.assert_array_equal(result[:, :15], self.frame[:, :15])
        np.testing.assert_array_equal(result[140:], self.frame[140:])
        np.testing.assert_array_equal(self.frame, before)

    def test_zero_strength_is_an_exact_bypass(self):
        restored = 255 - self.frame
        result = blend_mouth_detail(self.frame, restored, self.points, strength=0)
        np.testing.assert_array_equal(result, self.frame)

    def test_extreme_detail_clips_without_uint8_wrap(self):
        self.frame[:] = 250
        restored = np.zeros_like(self.frame)
        restored[95:110:2, 40:80] = 255
        result = blend_mouth_detail(self.frame, restored, self.points)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(int(result[99, 60, 0]), 255)

    def test_invalid_geometry_and_strength_fail_explicitly(self):
        for points in (self.points[:5], np.full((68, 2), np.nan), np.zeros((68, 2))):
            with self.subTest(points=points.shape), self.assertRaises(ValueError):
                blend_mouth_detail(self.frame, self.frame, points)
        with self.assertRaises(ValueError):
            blend_mouth_detail(self.frame, self.frame[:40], self.points)
        for strength in (-1, 1.1, float("nan")):
            with self.subTest(strength=strength), self.assertRaises(ValueError):
                blend_mouth_detail(self.frame, self.frame, self.points, strength=strength)

    def test_alignment_is_finite_invertible_and_repeatable(self):
        transform = face_alignment(self.points)
        self.assertEqual(transform.shape, (2, 3))
        self.assertTrue(np.isfinite(transform).all())
        self.assertGreater(np.linalg.det(transform[:, :2]), 0)
        np.testing.assert_array_equal(transform, face_alignment(self.points))


if __name__ == "__main__":
    unittest.main()

"""Actual checkpoint regression: RUN_AVATAR_GPU_TESTS=1 with avatar interpreter."""

import os
import unittest
from pathlib import Path


@unittest.skipUnless(os.environ.get("RUN_AVATAR_GPU_TESTS") == "1", "Optional real GPU fixture")
class MouthRestorationGPURegression(unittest.TestCase):
    def test_accelerated_output_retains_fp32_mouth_detail_and_fixed_noise(self):
        import cv2
        import numpy as np
        import torch

        from scripts.livetalking_restore import MouthDetailRestorer

        torch.set_num_threads(4)
        root = Path(__file__).resolve().parents[1]
        frame = cv2.imread(
            str(root / "output/avatar-quality-review/muse-dwpose-123/source/00000060.png")
        )
        points = np.load(
            root / "output/avatar-quality-review/mouth-detail-probe/source-landmarks.npy"
        )[60]
        self.assertIsNotNone(frame, "Prepare the documented 123 clip fixture first")
        model = MouthDetailRestorer(compile_model=False)
        accelerated = model.restore(frame, points)
        repeated = model.restore(frame, points)
        np.testing.assert_array_equal(accelerated, repeated)
        model.mixed_precision = False
        reference = model.restore(frame, points)
        center = points[48:60].mean(0).astype(int)
        x, y = center
        roi = (slice(y - 25, y + 25), slice(x - 45, x + 45))
        difference = np.abs(accelerated[roi].astype(float) - reference[roi].astype(float))
        self.assertLess(float(difference.mean()), 1.0)
        self.assertLess(float(np.percentile(difference, 99)), 4.0)
        # A flat/blurred mouth must fail even when every output pixel is finite.
        generated_energy = cv2.Laplacian(frame[roi], cv2.CV_32F).var()
        restored_energy = cv2.Laplacian(accelerated[roi], cv2.CV_32F).var()
        self.assertGreater(restored_energy, generated_energy * 1.15)


if __name__ == "__main__":
    unittest.main()

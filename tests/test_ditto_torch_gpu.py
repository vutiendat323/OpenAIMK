"""Real-checkpoint equivalence, including changing audio-driven keypoints."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("RUN_AVATAR_GPU_TESTS") == "1", "optional GPU check")
class DittoTorchTests(unittest.TestCase):
    def test_optimized_renderer_preserves_pixels_and_motion(self):
        import numpy as np
        import torch

        sys.path.insert(0, str(ROOT / ".runtime/Ditto"))
        from core.models.decoder import Decoder
        from core.models.warp_network import WarpNetwork

        from scripts.ditto_torch import FusedTorchRenderer

        torch.set_num_threads(4)
        model_dir = ROOT / ".runtime/Ditto/checkpoints/ditto_pytorch/models"
        inputs_dir = ROOT / "output/avatar-quality-review/ditto-torch-benchmark"
        warp = WarpNetwork(str(model_dir / "warp_network.pth"))
        decode = Decoder(str(model_dir / "decoder.pth"))
        samples = [np.load(inputs_dir / f"input-{i}.npz") for i in (0, 15, 30, 45, 60)]
        # Exercise the upstream numpy -> GPU -> numpy -> GPU path as reference.
        reference = [decode(warp(s["feature"], s["source"], s["driving"])) for s in samples]
        optimized = FusedTorchRenderer(warp.model, decode.model)
        results = [optimized(s["feature"], s["source"], s["driving"]) for s in samples]
        self.assertEqual(results[0].shape, (512, 512, 3))
        self.assertTrue(np.isfinite(results).all())
        delta = np.abs(np.asarray(results) - np.asarray(reference))
        self.assertLess(float(delta.mean()), 0.1)
        self.assertLess(float(np.percentile(delta, 99.9)), 1.0)
        self.assertLess(float(delta.max()), 2.0)
        # Ensure the optimized graph consumes new frames rather than stale inputs.
        self.assertGreater(float(np.abs(results[0] - results[-1]).mean()), 1.0)

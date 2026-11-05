"""Exact ROI decoding preserves global normalization, weights and pixel scale."""

import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".runtime/Ditto"))
from core.models.modules.spade_generator import SPADEDecoder

from scripts.ditto_roi import MouthDecoder


@pytest.mark.parametrize("roi", [(16, 24, 48, 56), (20, 20, 44, 48)])
def test_partial_decoder_matches_full_decoder_inside_roi(roi):
    torch.set_num_threads(2)
    torch.manual_seed(17)
    decoder = SPADEDecoder(block_expansion=2, max_features=16, out_channels=2).eval()
    for module in decoder.modules():
        if hasattr(module, "weight_orig"):
            torch.nn.utils.remove_spectral_norm(module)
    partial = MouthDecoder(decoder, roi)
    with torch.no_grad():
        for _ in range(2):
            feature = torch.randn(1, 8, 8, 8)
            reference, result = decoder(feature), partial(feature)
            x0, y0, x1, y1 = roi
            torch.testing.assert_close(
                result[:, :, y0:y1, x0:x1], reference[:, :, y0:y1, x0:x1], rtol=2e-5, atol=2e-6
            )
            assert not result[:, :, :y0].any()


def test_roi_must_have_pixel_shuffle_alignment():
    with pytest.raises(ValueError):
        MouthDecoder(torch.nn.Identity(), (15, 24, 48, 56))

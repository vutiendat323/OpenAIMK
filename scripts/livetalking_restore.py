"""Optional local mouth restoration, independent of the native voice pipeline."""

import sys
from pathlib import Path

import cv2
import numpy as np
import torch

from trendcoffee.avatar_restoration import blend_mouth_detail, face_alignment

ROOT = Path(__file__).resolve().parents[1]


class MouthDetailRestorer:
    def __init__(self, *, compile_model=True, mixed_precision=True):
        # Isolated optional packages; the API/voice environment never imports these.
        sys.path.insert(0, str(ROOT / ".runtime/muse-prep-packages"))
        import torchvision.transforms.functional as functional

        # BasicSR 1.4.2 uses this former torchvision module name.
        sys.modules.setdefault("torchvision.transforms.functional_tensor", functional)
        from gfpgan.archs.gfpganv1_clean_arch import GFPGANv1Clean

        model = GFPGANv1Clean(
            out_size=512,
            num_style_feat=512,
            channel_multiplier=2,
            decoder_load_path=None,
            fix_decoder=False,
            num_mlp=8,
            input_is_latent=True,
            different_w=True,
            narrow=1,
            sft_half=True,
        )
        weights = torch.load(
            ROOT / ".runtime/LiveTalking/models/restoration/GFPGANv1.4.pth",
            map_location="cpu",
            weights_only=True,
        )
        model.load_state_dict(weights["params_ema"], strict=True)
        # StyleGAN's weight-demodulation reduction overflows with half() weights.
        # Keep parameters/reductions in FP32; autocast accelerates convolutions.
        self.model = model.eval().cuda()
        self.mixed_precision = mixed_precision
        if compile_model:
            self.model = torch.compile(self.model, mode="reduce-overhead", fullgraph=True)

    @torch.no_grad()
    def restore(self, frame, points, *, strength=0.75):
        matrix = face_alignment(points)
        aligned = cv2.warpAffine(
            frame, matrix, (512, 512), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
        tensor = torch.from_numpy(
            cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB).transpose(2, 0, 1).copy()
        ).to(device="cuda", dtype=torch.float32)[None]
        tensor = tensor / 127.5 - 1
        torch.compiler.cudagraph_mark_step_begin()
        # Fixed noise prevents stochastic frame-to-frame texture flicker.
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=self.mixed_precision):
            prediction = self.model(tensor, return_rgb=False, randomize_noise=False)[0]
        pixels = prediction[0].float().cpu().numpy().transpose(1, 2, 0)
        if not np.isfinite(pixels).all():
            raise RuntimeError("nonfinite_mouth_restoration")
        restored = cv2.cvtColor(
            np.rint((np.clip(pixels, -1, 1) + 1) * 127.5).astype(np.uint8), cv2.COLOR_RGB2BGR
        )
        restored = cv2.warpAffine(
            restored,
            cv2.invertAffineTransform(matrix),
            (frame.shape[1], frame.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        return blend_mouth_detail(frame, restored, points, strength=strength)

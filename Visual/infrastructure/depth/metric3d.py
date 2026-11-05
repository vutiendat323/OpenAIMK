"""
Metric3Dv2 monocular metric depth estimator.

Wraps the Metric3D ViT-Small model with the canonical-camera-space pipeline:
preprocess → inference → un-pad + upsample → de-canonicalise → metric depth map.

Supports FP16 inference for ~2× speedup on supported GPUs.
"""

import logging
import os
import sys
from typing import Optional, Tuple

import numpy as np
import torch

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metric3D's mono/utils/comm.py imports from mmcv.utils, but the only usage
# (collect_env) is in a commented-out function.  We inject a minimal shim
# package so that the full mmcv installation is not required.
# ---------------------------------------------------------------------------
_SHIM_DIR = os.path.join(os.path.dirname(__file__), "_shim")
if _SHIM_DIR not in sys.path:
    sys.path.insert(0, _SHIM_DIR)

# Make the local Metric3D code importable.
_METRIC3D_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "Metric3D")
if _METRIC3D_DIR not in sys.path:
    sys.path.insert(0, _METRIC3D_DIR)

from mmengine import Config

from mono.model.monodepth_model import get_configured_monodepth_model
from Visual.infrastructure.depth.transforms import preprocess_for_metric3d, postprocess_depth


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
_MODEL_SPECS = {
    "vit_small": {
        "cfg_file": "mono/configs/HourglassDecoder/vit.raft5.small.py",
        "ckpt_url": "https://huggingface.co/JUGGHM/Metric3D/resolve/main/metric_depth_vit_small_800k.pth",
        "input_size": (616, 1064),
    },
    "vit_large": {
        "cfg_file": "mono/configs/HourglassDecoder/vit.raft5.large.py",
        "ckpt_url": "https://huggingface.co/JUGGHM/Metric3D/resolve/main/metric_depth_vit_large_800k.pth",
        "input_size": (616, 1064),
    },
    "vit_giant2": {
        "cfg_file": "mono/configs/HourglassDecoder/vit.raft5.giant2.py",
        "ckpt_url": "https://huggingface.co/JUGGHM/Metric3D/resolve/main/metric_depth_vit_giant2_800k.pth",
        "input_size": (616, 1064),
    },
}


class DepthEstimator:
    """
    Metric3Dv2 monocular depth estimator.

    Predicts a dense metric depth map from a single RGB image using the
    canonical-camera-space approach.  Supports FP16 for faster GPU inference.
    """

    def __init__(
        self,
        variant: str = "vit_small",
        device: str = "cpu",
        use_half: bool = False,
        input_size: Optional[Tuple[int, int]] = None,
    ):
        """
        Args:
            variant: One of 'vit_small', 'vit_large', 'vit_giant2'.
            device: Torch device string.
            use_half: Use FP16 (half precision) for 2× faster GPU inference.
            input_size: (H, W) override for the model input.  Smaller is much
                faster and mostly shifts depth by a constant scale, which the
                body distances scale with -- so re-check readings after changing it.
        """
        if variant not in _MODEL_SPECS:
            raise ValueError(
                f"Unknown Metric3D variant '{variant}'. "
                f"Choose from: {list(_MODEL_SPECS.keys())}"
            )

        spec = _MODEL_SPECS[variant]
        self._input_size = input_size or spec["input_size"]
        self._use_half = use_half and ("cuda" in device)

        # Build model from config
        cfg_path = os.path.join(_METRIC3D_DIR, spec["cfg_file"])
        cfg = Config.fromfile(cfg_path)
        self._model = get_configured_monodepth_model(cfg)

        # Download & load weights
        state_dict = torch.hub.load_state_dict_from_url(
            spec["ckpt_url"], progress=True
        )["model_state_dict"]
        self._model.load_state_dict(state_dict, strict=False)

        self._model.to(device)
        if self._use_half:
            self._model.half()  # Convert all parameters to FP16
        self._model.eval()
        self._device = device

        # Patch decoder modules that hardcode device="cuda" so they
        # respect the actual device the model was moved to — without
        # modifying the Metric3D vendored source.
        self._patch_decoder_device()

    # ------------------------------------------------------------------
    # Device patching — Metric3D decoders hardcode device="cuda"
    # ------------------------------------------------------------------
    def _patch_decoder_device(self) -> None:
        """Patch Metric3D decoder modules so they use the model's device.

        The vendored Metric3D code hardcodes ``device='cuda'`` in
        ``get_bins()`` and ``create_mesh_grid()``.  When running on CPU
        (or a non-default CUDA device) those calls would fail.  This
        method finds those modules in the loaded model and replaces the
        methods with versions that derive the device from the module's
        own parameters — which always match the device the model was
        moved to via ``self._model.to(device)``.
        """
        import math as _math
        import types as _types

        def _make_get_bins(_orig):
            def patched(self, bins_num):
                dev = next(self.parameters()).device
                depth_bins_vec = torch.linspace(
                    _math.log(self.min_val), _math.log(self.max_val),
                    bins_num, device=dev,
                )
                return torch.exp(depth_bins_vec)
            return patched

        def _make_create_mesh_grid(_orig):
            def patched(self, height, width, batch, device=None, set_buffer=True):
                if device is None:
                    device = next(self.parameters()).device
                y, x = torch.meshgrid(
                    [torch.arange(0, height, dtype=torch.float32, device=device),
                     torch.arange(0, width, dtype=torch.float32, device=device)],
                    indexing='ij',
                )
                meshgrid = torch.stack((x, y))
                return meshgrid.unsqueeze(0).repeat(batch, 1, 1, 1)
            return patched

        for module in self._model.modules():
            cls = type(module)
            if hasattr(cls, 'get_bins') and 'get_bins' in cls.__dict__:
                orig = cls.__dict__['get_bins']
                # Only patch if it was defined on this concrete class
                module.get_bins = _types.MethodType(
                    _make_get_bins(orig), module,
                )
            if hasattr(cls, 'create_mesh_grid') and 'create_mesh_grid' in cls.__dict__:
                module.create_mesh_grid = _types.MethodType(
                    _make_create_mesh_grid(None), module,
                )

    @property
    def device(self) -> str:
        return self._device

    @property
    def input_size(self) -> Tuple[int, int]:
        return self._input_size

    def estimate(
        self,
        rgb: np.ndarray,
        intrinsics: Tuple[float, float, float, float],
        canonical_to_real_scale: float,
    ) -> np.ndarray:
        """
        Estimate a metric depth map from an RGB image.

        Args:
            rgb: RGB image (H, W, 3), uint8.
            intrinsics: Camera (fx, fy, cx, cy).
            canonical_to_real_scale: Factor fx / 1000.0.

        Returns:
            Metric depth map (H, W), float32, in metres.
        """
        tensor, meta = preprocess_for_metric3d(
            rgb, self._input_size, intrinsics, self._device
        )

        # FP16 autocast — automatically uses FP16 for matmul/conv,
        # keeps FP32 where needed for numerical stability.
        with torch.no_grad():
            if self._use_half:
                with torch.amp.autocast("cuda", dtype=torch.float16):
                    pred_depth, _confidence, _output_dict = self._model.inference(
                        {"input": tensor}
                    )
            else:
                pred_depth, _confidence, _output_dict = self._model.inference(
                    {"input": tensor}
                )

        # Ensure output is FP32 for postprocessing
        if pred_depth.dtype == torch.float16:
            pred_depth = pred_depth.float()

        # --- diagnostic: log canonical depth stats (before scaling) ---
        canon = pred_depth.squeeze()
        t, b = meta["pad_top"], meta["pad_bottom"]
        l, r = meta["pad_left"], meta["pad_right"]
        h_pad, w_pad = canon.shape
        canon_unpad = canon[t:h_pad - b, l:w_pad - r]
        _log.debug(
            "canonical_depth: min=%.4f max=%.4f mean=%.4f med=%.4f | "
            "canonical_to_real_scale=%.6f (fx=%.1f)",
            float(canon_unpad.min()), float(canon_unpad.max()),
            float(canon_unpad.mean()), float(canon_unpad.median()),
            canonical_to_real_scale,
            canonical_to_real_scale * 1000.0,  # back-compute fx
        )

        # De-canonicalise with the focal length of the *resized* image, not
        # the original one: preprocess shrinks the frame by meta["scale"] to
        # fit the model input, which scales the effective focal by the same
        # factor.  Metric3D's own pipeline does this (hubconf.py:163 scales
        # the intrinsic before hubconf.py:197 divides it by 1000), and
        # dropping it inflated every reading by 1/scale — 1.56x at the
        # 308x532 input size this config runs.
        depth_map = postprocess_depth(
            pred_depth, meta, canonical_to_real_scale * meta["scale"],
        )

        # --- diagnostic: log real-world depth stats (after scaling) ---
        _log.debug(
            "real_depth: min=%.4f max=%.4f mean=%.4f med=%.4f | shape=%s",
            float(depth_map.min()), float(depth_map.max()),
            float(depth_map.mean()), float(np.median(depth_map)),
            depth_map.shape,
        )

        return depth_map

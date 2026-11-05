"""Metric3D input and output transforms, and depth-map sampling.

Keep-ratio resize, pad and normalise an RGB frame for the model; un-pad,
upsample and de-canonicalise its prediction back to a metric depth map.
Used by the Metric3D estimator; sample_depth_at_bbox by the evaluation tool.
"""

import logging
from typing import Tuple

import cv2
import numpy as np
import torch

_log = logging.getLogger(__name__)

# ImageNet mean and std used by Metric3D.
_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
_STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)

def preprocess_for_metric3d(
    rgb: np.ndarray,
    input_size: Tuple[int, int],
    intrinsics: Tuple[float, float, float, float],
    device: str = "cpu",
) -> Tuple[torch.Tensor, dict]:
    """
    Preprocess an RGB image for Metric3D inference.

    1. Keep-ratio resize to fit *input_size*.
    2. Scale intrinsics to match.
    3. Centre-pad with mean colour to exact *input_size*.
    4. Normalise with ImageNet mean/std.

    Args:
        rgb: Input image in RGB order, shape (H, W, 3), dtype uint8.
        input_size: Target (height, width) for the model.
        intrinsics: Original camera (fx, fy, cx, cy).
        device: Torch device string.

    Returns:
        (tensor, meta) where tensor has shape (1, 3, H_pad, W_pad) and
        meta is a dict with keys needed for postprocessing:
            'scale', 'pad_top', 'pad_bottom', 'pad_left', 'pad_right',
            'original_shape', 'scaled_intrinsics'.
    """
    h, w = rgb.shape[:2]
    target_h, target_w = input_size

    # --- keep-ratio resize ---
    scale = min(target_h / h, target_w / w)
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # scale intrinsics accordingly
    fx, fy, cx, cy = intrinsics
    scaled_intrinsics = (fx * scale, fy * scale, cx * scale, cy * scale)

    # --- centre pad ---
    pad_h = target_h - new_h
    pad_w = target_w - new_w
    pad_top = pad_h // 2
    pad_bottom = pad_h - pad_top
    pad_left = pad_w // 2
    pad_right = pad_w - pad_left

    padded = cv2.copyMakeBorder(
        resized,
        pad_top, pad_bottom, pad_left, pad_right,
        cv2.BORDER_CONSTANT,
        value=_MEAN.tolist(),
    )

    # --- normalise ---
    padded_f = padded.astype(np.float32)
    padded_f = (padded_f - _MEAN) / _STD

    # to tensor: HWC → CHW → BCHW
    tensor = torch.from_numpy(padded_f.transpose(2, 0, 1)).float()
    tensor = tensor.unsqueeze(0).to(device)

    meta = {
        "scale": scale,
        "pad_top": pad_top,
        "pad_bottom": pad_bottom,
        "pad_left": pad_left,
        "pad_right": pad_right,
        "original_shape": (h, w),
        "scaled_intrinsics": scaled_intrinsics,
    }
    return tensor, meta


def postprocess_depth(
    pred_depth: torch.Tensor,
    meta: dict,
    canonical_to_real_scale: float,
) -> np.ndarray:
    """
    Postprocess a Metric3D depth prediction back to original image space.

    Steps: un-pad → upsample to original resolution → de-canonicalise.

    Args:
        pred_depth: Raw model output tensor, shape (1, 1, H_pad, W_pad) or similar.
        meta: Dict returned by *preprocess_for_metric3d*.
        canonical_to_real_scale: factor = fx / 1000.0

    Returns:
        Metric depth map as a float32 numpy array, shape (original_h, original_w).
    """
    # Remove batch & channel dims → (H_pad, W_pad)
    depth = pred_depth.squeeze()

    # un-pad
    t, b = meta["pad_top"], meta["pad_bottom"]
    l, r = meta["pad_left"], meta["pad_right"]
    h_pad, w_pad = depth.shape
    depth = depth[t : h_pad - b, l : w_pad - r]

    # upsample to original resolution
    orig_h, orig_w = meta["original_shape"]
    depth = torch.nn.functional.interpolate(
        depth[None, None, :, :],
        size=(orig_h, orig_w),
        mode="bilinear",
        align_corners=False,
    ).squeeze()

    # de-canonicalise → real metric depth
    depth = depth * canonical_to_real_scale
    depth = depth.cpu().numpy().astype(np.float32)
    return depth
def sample_depth_at_bbox(
    depth_map: np.ndarray,
    bbox: Tuple[float, float, float, float],
    method: str = "center",
) -> float:
    """
    Sample the depth value for a person from the full-frame depth map.

    Args:
        depth_map: Metric depth array, shape (H, W).
        bbox: (x1, y1, x2, y2) in pixel coordinates.
        method: Sampling strategy.
            - "bottom_center": midpoint of the bottom edge (feet region).
            - "center": centre of the bounding box.
            - "median": median depth inside the bbox (most robust).

    Returns:
        Estimated distance in metres.
    """
    x1, y1, x2, y2 = [int(v) for v in bbox]
    h, w = depth_map.shape

    # clamp coordinates to valid range
    x1 = max(0, min(x1, w - 1))
    x2 = max(x1 + 1, min(x2, w))
    y1 = max(0, min(y1, h - 1))
    y2 = max(y1 + 1, min(y2, h))

    if method == "bottom_center":
        cx = (x1 + x2) // 2
        cy = y2 - 1  # bottom row
        return float(depth_map[cy, cx])

    elif method == "center":
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return float(depth_map[cy, cx])

    elif method == "median":
        crop = depth_map[y1:y2, x1:x2]
        result = float(np.median(crop))
        _log.debug(
            "sample_depth: bbox=(%d,%d,%d,%d) crop=%dx%d "
            "crop_min=%.4f crop_max=%.4f crop_mean=%.4f crop_med=%.4f",
            x1, y1, x2, y2, crop.shape[1], crop.shape[0],
            float(crop.min()), float(crop.max()),
            float(crop.mean()), result,
        )
        return result

    else:
        raise ValueError(f"Unknown sampling method: {method}")

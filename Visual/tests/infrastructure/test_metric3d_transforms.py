"""Depth-map sampling at a box (used by the evaluation tool)."""

import numpy as np

from Visual.infrastructure.depth.transforms import sample_depth_at_bbox


def test_sample_depth_center():
    """Depth at center of bbox returns correct value."""
    depth_map = np.full((480, 640), 1.5, dtype=np.float32)
    bbox = (200.0, 150.0, 300.0, 250.0)  # center at (250, 200)
    dist = sample_depth_at_bbox(depth_map, bbox, method="center")
    assert dist == 1.5

def test_sample_depth_default_method_is_center():
    """Default sampling method should be 'center' for face detection."""
    import inspect
    sig = inspect.signature(sample_depth_at_bbox)
    assert sig.parameters["method"].default == "center"

def test_sample_depth_median():
    depth_map = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
        [7.0, 8.0, 9.0],
    ], dtype=np.float32)
    dist = sample_depth_at_bbox(depth_map, (0, 0, 3, 3), method="median")
    assert dist == 5.0

def test_sample_depth_clamps_to_bounds():
    depth_map = np.full((100, 100), 2.0, dtype=np.float32)
    # Bbox extends beyond frame — should clamp
    dist = sample_depth_at_bbox(depth_map, (-50, -50, 150, 150), method="center")
    # Center of clamped bbox should be near (75, 75) — depth 2.0
    assert 1.9 <= dist <= 2.1

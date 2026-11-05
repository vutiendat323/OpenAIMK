"""Geometry that turns what the models see into metres, and box maths.

Face distance from five landmarks (PnP), body distance from a depth map
under a person box, face-in-body matching, IoU and box conversions.
"""

from typing import Tuple
import cv2
import numpy as np


def body_distance(
    depth_map: np.ndarray,
    bbox: Tuple[float, float, float, float],
    shrink: float = 0.5,
    percentile: float = 20.0,
) -> float | None:
    """Distance to a person from their box on the depth map, or None.

    A body box holds far more background than a face box does: gaps between
    arms, slivers past the shoulders.  A median over the box lets that
    background in, and a person walking sideways then reads metres too far --
    the original 1.0 m -> 1.7-2.0 m bug.  So: keep only the middle *shrink* of
    the box, where the body actually is, and take a low *percentile* of what is
    left, which leans on the pixels nearest the camera.
    """
    x1, y1, x2, y2 = bbox
    if x2 <= x1 or y2 <= y1:
        return None
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    half_w, half_h = (x2 - x1) * shrink / 2.0, (y2 - y1) * shrink / 2.0
    h, w = depth_map.shape
    xa, xb = int(max(0, cx - half_w)), int(min(w, cx + half_w + 1))
    ya, yb = int(max(0, cy - half_h)), int(min(h, cy + half_h + 1))
    if xb <= xa or yb <= ya:
        return None
    core = depth_map[ya:yb, xa:xb]
    valid = core[np.isfinite(core) & (core > 0)]
    if valid.size == 0:
        return None
    return float(np.percentile(valid, percentile))


def box_contains_center(outer, inner) -> bool:
    """True when *inner*'s centre falls inside *outer* — face to body match."""
    cx = (inner[0] + inner[2]) / 2.0
    cy = (inner[1] + inner[3]) / 2.0
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


# Generic adult face at the 5 SCRFD landmarks (eyes, nose tip, mouth corners),
# metres, OpenCV camera axes (x right, y down, z away from the camera).  The
# eye spacing sets the scale; the other points pin down the head pose.
_FACE_MODEL = np.array([
    [-0.0315, 0.000, 0.000],
    [0.0315, 0.000, 0.000],
    [0.000, 0.040, -0.020],
    [-0.025, 0.070, -0.005],
    [0.025, 0.070, -0.005],
])
# Landmarks no rigid face fits (profile view, occlusion) are rejected.  Scaled
# to the eye spacing: a near face tolerates more generic-model mismatch in px.
_MAX_REPROJ_FRAC = 0.15


def face_distance(landmarks, camera_matrix: np.ndarray, ipd_m: float = 0.063) -> float | None:
    """Metric distance to a face from its 5 landmarks, or None if unusable.

    Solves the head pose (PnP) against a generic face scaled to *ipd_m*, so a
    turned head is handled by the geometry instead of reading as farther
    away: simulated, raw eye spacing reads +20% at 40 deg yaw, PnP stays
    within 1%.  The error budget is the person's own IPD against *ipd_m*
    (adult 63 mm +/- 3.5 mm, ~5.5%) -- ``Config.face_ipd_m`` is the knob.
    """
    if landmarks is None:
        return None
    pts = np.asarray(landmarks, dtype=np.float64).reshape(5, 2)
    ipd_px = float(np.linalg.norm(pts[1] - pts[0]))
    if ipd_px < 8.0:                 # beyond ~5 m; PnP on a speck is noise
        return None
    model = _FACE_MODEL * (ipd_m / 0.063)
    ok, rvec, tvec = cv2.solvePnP(model, pts, camera_matrix, None,
                                  flags=cv2.SOLVEPNP_SQPNP)
    if not ok:
        return None
    proj, _ = cv2.projectPoints(model, rvec, tvec, camera_matrix, None)
    if np.abs(proj.reshape(5, 2) - pts).max() > _MAX_REPROJ_FRAC * ipd_px:
        return None
    z = float(tvec[2, 0])
    return z if 0.15 < z < 6.0 else None


def xyxy_to_xywh(bbox: np.ndarray) -> np.ndarray:
    """Convert [x1, y1, x2, y2] → [cx, cy, w, h]."""
    out = bbox.copy()
    out[0] = (bbox[0] + bbox[2]) / 2.0  # cx
    out[1] = (bbox[1] + bbox[3]) / 2.0  # cy
    out[2] = bbox[2] - bbox[0]           # w
    out[3] = bbox[3] - bbox[1]           # h
    return out


def xywh_to_xyxy(bbox: np.ndarray) -> np.ndarray:
    """Convert [cx, cy, w, h] → [x1, y1, x2, y2]."""
    out = bbox.copy()
    out[0] = bbox[0] - bbox[2] / 2.0
    out[1] = bbox[1] - bbox[3] / 2.0
    out[2] = bbox[0] + bbox[2] / 2.0
    out[3] = bbox[1] + bbox[3] / 2.0
    return out


def iou(bbox_a: np.ndarray, bbox_b: np.ndarray) -> float:
    """
    Compute IoU between two bounding boxes in [x1, y1, x2, y2] format.
    Returns float in [0, 1].
    """
    xa = max(bbox_a[0], bbox_b[0])
    ya = max(bbox_a[1], bbox_b[1])
    xb = min(bbox_a[2], bbox_b[2])
    yb = min(bbox_a[3], bbox_b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    area_a = (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1])
    area_b = (bbox_b[2] - bbox_b[0]) * (bbox_b[3] - bbox_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def iou_batch(detections: np.ndarray, tracks: np.ndarray) -> np.ndarray:
    """
    Compute IoU matrix between all detections and all tracks.

    Args:
        detections: (N, 4)  [x1, y1, x2, y2]
        tracks:     (M, 4)  [x1, y1, x2, y2]

    Returns:
        (N, M) matrix of IoU scores.
    """
    N, M = len(detections), len(tracks)
    iou_matrix = np.zeros((N, M), dtype=np.float32)
    for i in range(N):
        for j in range(M):
            iou_matrix[i, j] = iou(detections[i], tracks[j])
    return iou_matrix

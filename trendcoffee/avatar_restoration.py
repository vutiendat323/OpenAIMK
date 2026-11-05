"""Face alignment and local mouth-detail compositing for the avatar worker."""

import cv2
import numpy as np

FACE_TEMPLATE = np.array(
    [
        [192.98138, 239.94708],
        [318.90277, 240.1936],
        [256.63416, 314.01935],
        [201.26117, 371.41043],
        [313.08905, 371.15118],
    ],
    dtype=np.float32,
)


def _landmarks(points):
    points = np.asarray(points, dtype=np.float32)
    if points.shape != (68, 2) or not np.isfinite(points).all():
        raise ValueError("invalid_restoration_landmarks")
    if np.linalg.norm(points[54] - points[48]) < 2:
        raise ValueError("degenerate_restoration_mouth")
    return points


def face_alignment(points):
    points = _landmarks(points)
    five = np.array(
        [points[36:42].mean(0), points[42:48].mean(0), points[30], points[48], points[54]],
        dtype=np.float32,
    )
    matrix = cv2.estimateAffinePartial2D(five, FACE_TEMPLATE, method=cv2.LMEDS)[0]
    if matrix is None or not np.isfinite(matrix).all() or np.linalg.det(matrix[:, :2]) <= 0:
        raise ValueError("invalid_restoration_alignment")
    return matrix


def blend_mouth_detail(frame, restored, points, *, strength=0.75):
    """Keep generated lip timing/color; replace only local high-frequency detail.

    Full face restoration changes identity, lipstick and lighting. Subtracting its
    low frequencies prevents that broad recoloring. Neither source mouth pixels
    nor an unrelated video frame are mixed into the synthesized mouth.
    """
    points = _landmarks(points)
    if not np.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("invalid_restoration_strength")
    if frame.shape != restored.shape or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("invalid_restoration_frame")
    if frame.dtype != np.uint8 or restored.dtype != np.uint8:
        raise ValueError("invalid_restoration_pixels")
    if strength == 0:
        return frame.copy()
    center = points[48:60].mean(0)
    width = np.linalg.norm(points[54] - points[48])
    # Work in a bounded ROI. Pixels outside it, including eyes and hair, are exact.
    margin = int(width * 1.05) + 2
    x1, y1 = np.maximum(np.floor(center - margin).astype(int), 0)
    x2, y2 = np.minimum(np.ceil(center + margin).astype(int), frame.shape[1::-1])
    if x2 <= x1 or y2 <= y1:
        raise ValueError("restoration_mouth_outside_frame")
    mask = np.zeros((y2 - y1, x2 - x1), dtype=np.float32)
    cv2.ellipse(
        mask,
        tuple(np.rint(center - (x1, y1)).astype(int)),
        (max(1, int(width * 0.75)), max(1, int(width * 0.45))),
        0,
        0,
        360,
        1,
        -1,
    )
    mask = cv2.GaussianBlur(mask, (15, 15), 3)[..., None] * strength
    base = frame[y1:y2, x1:x2].astype(np.float32)
    detail = restored[y1:y2, x1:x2].astype(np.float32)
    base_high = base - cv2.GaussianBlur(base, (0, 0), 3)
    detail_high = detail - cv2.GaussianBlur(detail, (0, 0), 3)
    result = frame.copy()
    result[y1:y2, x1:x2] = np.rint(np.clip(base + (detail_high - base_high) * mask, 0, 255)).astype(
        np.uint8
    )
    return result

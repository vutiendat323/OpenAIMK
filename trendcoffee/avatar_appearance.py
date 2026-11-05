"""Preserve original source pixels outside the audio-driven mouth region."""

import cv2
import numpy as np

from .avatar_expression import source_expression_anchors
from .avatar_whole_face import prepare_closed_mouth


def register_source(registrar, path, *, shared_anchor=False, close_mouth=False, **kwargs):
    """Capture lip geometry during the registrar's existing landmark pass."""
    detector = registrar.source2info.landmark478
    regions, apertures, face_landmarks = [], [], []
    donor = None
    donor_points = None
    original_encode = registrar.source2info._img_crop_to_bchw256 if close_mouth else None

    def encode(image):
        nonlocal donor, donor_points
        if donor is None:
            if apertures[-1] > 0.06:
                raise ValueError("The mouth donor must be a real closed source frame")
            donor, donor_points = image.copy(), face_landmarks[-1].copy()
            return original_encode(image)
        prepared = prepare_closed_mouth(image, face_landmarks[-1], donor, donor_points)
        return original_encode(prepared)

    def capture(image):
        landmarks = detector(image)
        points = np.asarray(landmarks)[0, :, :2] * 512
        face_landmarks.append(points.copy())
        lips = points[[61, 291, 0, 17]]
        if not np.isfinite(lips).all():
            raise ValueError("Invalid source mouth landmarks")
        width = float(np.linalg.norm(lips[1] - lips[0]))
        if width <= 0:
            raise ValueError("Invalid source lip width")
        apertures.append(float(np.linalg.norm(points[14] - points[13]) / width))
        center = (lips.min(0) + lips.max(0)) / 2
        regions.append(
            (float(center[0]), float(center[1]), max(36, width * 0.82), max(36, width * 0.60))
        )
        return landmarks

    registrar.source2info.landmark478 = capture
    if close_mouth:
        registrar.source2info._img_crop_to_bchw256 = encode
    try:
        info = registrar(path, **kwargs)
    finally:
        registrar.source2info.landmark478 = detector
        if close_mouth:
            registrar.source2info._img_crop_to_bchw256 = original_encode
    if len(regions) != len(info["img_rgb_lst"]):
        raise ValueError("Source mouth landmarks do not match source frames")
    info["mouth_regions"] = regions
    info["mouth_apertures"] = apertures
    info["face_landmarks"] = face_landmarks
    if "x_s_info_lst" in info:
        info["mouth_expression_anchors"] = source_expression_anchors(
            [frame["exp"] for frame in info["x_s_info_lst"]], apertures, shared=shared_anchor
        )
    return info


def composite_mouth(frame_rgb, render_rgb, crop_to_frame, region, *, render_region=None):
    """Replace lips/lower jaw; leave source eyes, hair, clothing and background exact.

    The mask's interior fully replaces source lips, avoiding a double mouth.
    Its feathered rim follows the source affine transform. Only that small output
    region is warped; no additional neural model or GPU pass is introduced.
    """
    height, width = frame_rgb.shape[:2]
    matrix = np.asarray(crop_to_frame, dtype=np.float32)[:2].copy()
    render_matrix = matrix.copy()
    cx, cy, rx, ry = region
    if render_region is not None:
        px, py, prx, pry = render_region
        follow = np.array(
            [[rx / prx, 0, cx - px * rx / prx], [0, ry / pry, cy - py * ry / pry], [0, 0, 1]],
            dtype=np.float32,
        )
        render_matrix = render_matrix @ follow
    corners = (
        np.array(
            [
                [cx - rx - 2, cy - ry - 2, 1],
                [cx + rx + 2, cy - ry - 2, 1],
                [cx - rx - 2, cy + ry + 2, 1],
                [cx + rx + 2, cy + ry + 2, 1],
            ],
            dtype=np.float32,
        )
        @ matrix.T
    )
    left, top = np.maximum(np.floor(corners.min(0)), 0).astype(int)
    right, bottom = np.minimum(np.ceil(corners.max(0)), [width, height]).astype(int)
    result = frame_rgb.copy()
    if right <= left or bottom <= top:
        return result
    y, x = np.ogrid[:512, :512]
    distance = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    edge = np.clip((distance - 0.65) / 0.35, 0, 1)
    mask = (1 - edge * edge * (3 - 2 * edge)).astype(np.float32)
    matrix[:, 2] -= (left, top)
    render_matrix[:, 2] -= (left, top)
    size = (int(right - left), int(bottom - top))
    alpha = cv2.warpAffine(mask, matrix, size, flags=cv2.INTER_LINEAR).clip(0, 1)[..., None]
    generated = cv2.warpAffine(
        np.clip(render_rgb, 0, 255).astype(np.float32), render_matrix, size, flags=cv2.INTER_LINEAR
    )
    source = frame_rgb[top:bottom, left:right]
    result[top:bottom, left:right] = (
        np.rint(source * (1 - alpha) + generated * alpha).clip(0, 255).astype(np.uint8)
    )
    return result


def calm_source_frames(apertures, widths, poses, *, closed_threshold=0.06, width_tolerance=0.08):
    """For each frame, the calm closed-mouth frame with the closest head pose.

    A speaking source has open, pursed and widely smiling frames. A resting mouth
    built from those inherits their shape, so rest borrows appearance only from
    frames whose lips are closed at a typical width.
    """
    apertures, widths = np.asarray(apertures, float), np.asarray(widths, float)
    poses = np.asarray(poses, float)
    closed = np.flatnonzero(apertures <= closed_threshold)
    if not len(closed):
        closed = np.array([int(np.argmin(apertures))])
    typical = np.median(widths[closed])
    calm = [j for j in closed if abs(widths[j] - typical) <= width_tolerance * typical]
    calm = np.array(calm if calm else closed)
    gaps = np.abs(poses[:, None, :] - poses[None, calm, :]).sum(axis=2)
    # Equal pose gaps resolve to the nearest moment in the clip.
    gaps = gaps + 1e-6 * np.abs(np.arange(len(poses))[:, None] - calm[None, :])
    return [int(calm[k]) for k in gaps.argmin(axis=1)]


def blend_rest_mouth(own, calm, region):
    """Take only the mouth from a calm frame's face; the rest stays this frame's.

    Hair, jaw edge, neck and collar differ between source frames, so a whole face
    from another frame would misplace them.
    """
    cx, cy, rx, ry = region
    height, width = own.shape[:2]
    y, x = np.ogrid[:height, :width]
    distance = np.sqrt(((x - cx) / (rx * 1.35)) ** 2 + ((y - cy - ry * 0.1) / (ry * 1.5)) ** 2)
    edge = np.clip((distance - 0.6) / 0.4, 0, 1)
    mask = (1 - edge * edge * (3 - 2 * edge)).astype(np.float32)[..., None]
    return own * (1 - mask) + calm * mask

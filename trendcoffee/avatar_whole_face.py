"""Prepare source lips and blend each frame's own Ditto face without replacing its neck."""

import cv2
import numpy as np

OVAL = [
    10,
    338,
    297,
    332,
    284,
    251,
    389,
    356,
    454,
    323,
    361,
    288,
    397,
    365,
    379,
    378,
    400,
    377,
    152,
    148,
    176,
    149,
    150,
    136,
    172,
    58,
    132,
    93,
    234,
    127,
    162,
    21,
    54,
    103,
    67,
    109,
]
LIPS = [6, 12, 14, 17, 19, 20]
# Upper edge of both eyebrows (face-mesh ids): the paste starts here, the forehead stays the clip's.
BROWS = [70, 63, 105, 66, 107, 300, 293, 334, 296, 336]


def prepare_closed_mouth(image, points, donor, donor_points):
    """Prepare only the lips; features/geometry will both be extracted from this crop."""
    ring_ids = [
        61,
        146,
        91,
        181,
        84,
        17,
        314,
        405,
        321,
        375,
        291,
        409,
        270,
        269,
        267,
        0,
        37,
        39,
        40,
        185,
    ]
    source_eye = donor_points[263] - donor_points[33]
    target_eye = points[263] - points[33]
    scale = np.linalg.norm(target_eye) / np.linalg.norm(source_eye)
    rotation = np.arctan2(target_eye[1], target_eye[0]) - np.arctan2(source_eye[1], source_eye[0])
    cosine, sine = np.cos(rotation), np.sin(rotation)
    linear = np.array([[cosine, -sine], [sine, cosine]], np.float32) * scale
    source_center = (donor_points[61] + donor_points[291]) / 2
    target_center = (points[61] + points[291]) / 2
    matrix = np.column_stack([linear, target_center - linear @ source_center])
    mapped = donor_points @ linear.T + matrix[:, 2]
    eye = float(np.linalg.norm(target_eye))
    grow = max(2, int(eye * 0.03))
    ellipse = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow * 2 + 1, grow * 2 + 1))
    old = np.zeros(image.shape[:2], np.uint8)
    new = np.zeros_like(old)
    cv2.fillConvexPoly(old, cv2.convexHull(points[ring_ids].astype(np.int32)), 255)
    cv2.fillConvexPoly(new, cv2.convexHull(mapped[ring_ids].astype(np.int32)), 255)
    old = cv2.dilate(old, ellipse)
    new = cv2.dilate(new, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    # Old mouth and new lips both leave the frame's own skin: fill them from the skin around,
    # so no skin of the donor frame (its tone, halo or seam) is ever pasted.
    cleared = cv2.dilate(cv2.bitwise_or(old, new), np.ones((3, 3), np.uint8))
    patched = cv2.inpaint(image, cleared, 6, cv2.INPAINT_TELEA)
    edge = np.clip(cv2.distanceTransform(cleared, cv2.DIST_L2, 5) / 5, 0, 1)[..., None]
    skin = image * (1 - edge) + patched * edge  # no hard rim where the repair meets real skin
    aligned = cv2.warpAffine(donor, matrix, (image.shape[1], image.shape[0]))
    ring = (cv2.dilate(new, np.ones((9, 9), np.uint8)) > 0) & (new == 0)
    shift = np.median(skin[ring].astype(np.float32) - aligned[ring].astype(np.float32), axis=0)
    aligned = np.clip(aligned.astype(np.float32) + shift, 0, 255)
    alpha = np.clip(cv2.distanceTransform(new, cv2.DIST_L2, 5) / 3, 0, 1)[..., None]
    return np.rint(skin * (1 - alpha) + aligned * alpha).clip(0, 255).astype(np.uint8)


def pose_degrees(prediction):
    """Ditto's 66-bin angle code read as degrees, as Ditto itself reads it."""
    values = np.asarray(prediction, np.float32)
    if values.ndim > 1 and values.shape[1] == 66:
        weights = np.exp(values - values.max(axis=1, keepdims=True))
        weights /= weights.sum(axis=1, keepdims=True)
        return (weights * np.arange(66, dtype=np.float32)).sum(axis=1) * 3 - 97.5
    return values


def head_drive(own, voice, rest, alpha, gain, turn_gain=None):
    """The clip's own head pose plus the displacement the audio model predicts for it."""
    strength = alpha * gain
    result = {}
    for key in ("pitch", "yaw", "roll"):
        shift = pose_degrees(voice[key]) - pose_degrees(rest[key])
        # The eyes stay the clip's, looking at the camera: turning the face (yaw, pitch) moves the gaze
        # off the camera, tilting it (roll) does not, so turning can be given its own smaller gain.
        share = strength if turn_gain is None or key == "roll" else alpha * turn_gain
        result[key] = (pose_degrees(own[key]) + shift * share).astype(np.float32)
    for key in ("t", "scale"):
        result[key] = (own[key] + (voice[key] - rest[key]) * strength).astype(np.float32)
    return result


def speech_expression(source, voice, rest, lip_factor, alpha, lip_width=1.0):
    """Apply speech displacement only to Ditto's safe lip points, preserving anatomy."""
    result = source.reshape(21, 3).copy()
    delta = (voice - rest).reshape(21, 3).copy() * alpha
    vertical = delta[LIPS, 1]
    delta[LIPS, 1] = vertical.mean() + (vertical - vertical.mean()) * lip_factor
    # Sideways and forward lip motion is what reads as pursed "o" lips; opening is untouched.
    delta[LIPS, 0] *= lip_width
    delta[LIPS, 2] *= lip_width
    result[LIPS] += delta[LIPS]
    return result.reshape(source.shape)


def composite_whole_face(frame, generated, crop_to_frame, points):
    height, width = frame.shape[:2]
    crop_height, crop_width = generated.shape[:2]
    matrix = np.asarray(crop_to_frame, np.float32)[:2]
    mask = np.zeros((crop_height, crop_width), np.uint8)
    cv2.fillConvexPoly(mask, cv2.convexHull(points[OVAL].astype(np.int32)), 255)
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    eye_width = np.linalg.norm(points[33] - points[263])
    feather = max(4.0, float(eye_width) * 0.08)
    alpha = np.clip(distance / feather, 0, 1)
    # A turned head makes the decoder redraw hair on the forehead (dark wedges): keep the clip's
    # forehead and paste the generated face only from the brows down.
    ramp = max(3.0, float(eye_width) * 0.05)
    brow_top = float(points[BROWS, 1].min())
    rows = np.arange(crop_height, dtype=np.float32)[:, None]
    alpha = alpha * np.clip((rows - (brow_top - 2 * ramp)) / (2 * ramp), 0, 1)
    source_crop = cv2.warpAffine(
        frame, cv2.invertAffineTransform(matrix), (crop_width, crop_height)
    )
    # Match skin on the upper face; lips, teeth, hair and neck cannot set the offset.
    upper_skin = (distance > feather) & (np.indices(mask.shape)[0] < points[1, 1])
    shift = np.zeros(3, np.float32)
    if np.any(upper_skin):
        shift = np.median(
            source_crop[upper_skin].astype(np.float32) - generated[upper_skin], axis=0
        )
    generated = np.clip(generated + np.clip(shift, -20, 20), 0, 255)
    outline = points[OVAL] @ matrix[:, :2].T + matrix[:, 2]
    left, top = np.maximum(np.floor(outline.min(0)) - 2, 0).astype(int)
    right, bottom = np.minimum(np.ceil(outline.max(0)) + 3, [width, height]).astype(int)
    result = frame.copy()
    if right <= left or bottom <= top:
        return result
    local = matrix.copy()
    local[:, 2] -= [left, top]
    size = (int(right - left), int(bottom - top))
    warped = cv2.warpAffine(generated, local, size)
    alpha = cv2.warpAffine(alpha, local, size).clip(0, 1)[..., None]
    patch = frame[top:bottom, left:right]
    result[top:bottom, left:right] = (
        np.rint(patch * (1 - alpha) + warped * alpha).clip(0, 255).astype(np.uint8)
    )
    return result

"""Find the source clip's blink frames so the player can pass through them quickly."""

import numpy as np

# MediaPipe face-mesh ids: eyelid pair and the two corners of each eye.
EYES = ((159, 145, 33, 133), (386, 374, 362, 263))


def eye_openness(points):
    values = []
    for upper, lower, inner, outer in EYES:
        width = float(np.linalg.norm(points[outer] - points[inner]))
        values.append(float(np.linalg.norm(points[upper] - points[lower])) / max(width, 1e-6))
    return sum(values) / len(values)


def blink_flags(landmarks, closed_ratio=0.55):
    """True for frames whose eyes are much more closed than the clip's usual open eyes."""
    openness = np.array([eye_openness(points) for points in landmarks])
    if not len(openness):
        return []
    return [bool(value < openness.max() * closed_ratio) for value in openness]

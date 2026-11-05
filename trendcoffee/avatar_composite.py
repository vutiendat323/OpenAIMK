"""Wav2Lip face compositing; imported only by the local avatar environment."""

from functools import lru_cache

import cv2
import numpy as np


def _smoothstep(values):
    values = np.clip(values, 0, 1)
    return values * values * (3 - 2 * values)


@lru_cache(maxsize=32)
def _mouth_mask(height, width):
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    # Preserve original eyes/forehead. Fully replace the mouth; blending its
    # interior with the closed source lips would create a second mouth.
    vertical = _smoothstep((y - 0.40) / 0.20) * _smoothstep((1 - y) / 0.08)
    horizontal = _smoothstep(x / 0.15) * _smoothstep((1 - x) / 0.15)
    return (vertical * horizontal)[..., None]


def composite_face(frame, prediction, coords):
    y1, y2, x1, x2 = coords
    height, width = y2 - y1, x2 - x1
    generated = cv2.resize(np.clip(prediction, 0, 255).astype(np.uint8), (width, height))
    mask = _mouth_mask(height, width)
    result = frame.copy()
    source = frame[y1:y2, x1:x2]
    result[y1:y2, x1:x2] = np.rint(source * (1 - mask) + generated * mask).astype(np.uint8)
    return result

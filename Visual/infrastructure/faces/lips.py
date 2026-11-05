"""Lip opening from MediaPipe face landmarks (ONNX, Apache-2.0).

Model: Google's Face Landmarker landmark network converted to ONNX
(huggingface.co/naklitechie/face-landmarks-onnx): a 256x256 RGB [0, 1] face
crop in, 478 (x, y, z) points out.  11 ms per face on the laptop CPU.
"""
from __future__ import annotations

import cv2
import numpy as np
import onnxruntime as ort

_SIZE = 256
_UP, _LO, _LEFT, _RIGHT = 13, 14, 78, 308  # inner lips
_CROP_SCALE = 1.5  # MediaPipe's face-box expansion


class LipReader:
    """Inner-lip gap over inner-lip width for one face box."""

    def __init__(self, model_path: str):
        # CPU on purpose: 11 ms/face, and the GPU stays with SCRFD and depth.
        self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name
        self._dst = np.float32([[0, 0], [_SIZE, 0], [0, _SIZE]])

    def opening(self, frame_bgr: np.ndarray, box) -> float | None:
        x1, y1, x2, y2 = box[:4]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        half = _CROP_SCALE * max(x2 - x1, y2 - y1) / 2
        if half <= 0:
            return None
        src = np.float32([[cx - half, cy - half], [cx + half, cy - half], [cx - half, cy + half]])
        crop = cv2.warpAffine(frame_bgr, cv2.getAffineTransform(src, self._dst),
                              (_SIZE, _SIZE), borderMode=cv2.BORDER_CONSTANT)
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32)[None] / 255.0
        points = self._session.run(None, {self._input: rgb})[0].reshape(-1, 3)[:, :2]
        width = float(np.linalg.norm(points[_LEFT] - points[_RIGHT]))
        if width < 1.0:
            return None
        return float(np.linalg.norm(points[_UP] - points[_LO])) / width

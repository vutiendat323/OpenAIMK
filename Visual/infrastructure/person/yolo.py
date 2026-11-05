"""PersonDetector — YOLO11n person boxes, for people the face detector cannot see.

Tracks come from faces, so a customer who turns away disappears and the kiosk
starts its leave timer.  This answers the other question: is a *person* standing
there at all.  It runs inside the depth thread, on the same frame Metric3D reads,
so a box and the depth under it can never come from different frames.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np

_log = logging.getLogger(__name__)

_PERSON_CLASS = 0  # COCO


class PersonDetector:
    """Wraps an ultralytics YOLO model, filtered to the person class."""

    def __init__(self, model_path: str, conf_thresh: float = 0.4, device: str = "cpu"):
        from ultralytics import YOLO

        self._model = YOLO(model_path)
        self._conf = conf_thresh
        self._device = device

    def detect(self, frame_bgr: np.ndarray) -> List[Tuple[float, float, float, float, float]]:
        """Return ``[(x1, y1, x2, y2, confidence), ...]`` in frame pixels."""
        results = self._model.predict(
            frame_bgr, classes=[_PERSON_CLASS], conf=self._conf,
            device=self._device, verbose=False,
        )
        boxes = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                boxes.append((x1, y1, x2, y2, float(box.conf[0])))
        return boxes

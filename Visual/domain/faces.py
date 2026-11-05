"""A detected face: box, confidence, five landmarks.

What a face *is* to the rest of the service, whichever detector produced it.
The application's ports and the detectors both speak it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class FaceDetection:
    """One detected face."""

    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) in original frame coords
    confidence: float
    landmarks: Optional[List[Tuple[float, float]]] = None  # 5-point facial landmarks

    def to_tracker_tuple(self) -> Tuple[float, float, float, float, float]:
        """Convert to (x1, y1, x2, y2, confidence) for ByteTrack."""
        return (*self.bbox, self.confidence)

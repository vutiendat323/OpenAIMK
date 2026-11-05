"""Ports: what each model must be able to do, named by role.

The loops depend on these, not on SCRFD or Metric3D.  They are satisfied
structurally -- the infrastructure classes and the test stand-ins never import
this module or inherit from it -- so infrastructure depends on the domain
only.  There is no type checker; these are the readable statement of each
contract, and tests/application/test_ports.py keeps the real classes to it.
"""

from __future__ import annotations

from typing import Protocol, Sequence

import numpy as np

from Visual.domain.faces import FaceDetection

Box = tuple[float, float, float, float]            # x1, y1, x2, y2 in frame pixels


class FaceDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]: ...


class Tracker(Protocol):
    """Stable ids across frames.  A track has ``id``, ``bbox`` and
    ``time_since_update`` (0 when a detection confirmed it this frame)."""

    @property
    def active_tracks(self) -> list: ...

    def update(self, detections: Sequence[tuple], embeddings: list | None = None,
               ) -> list[tuple]: ...         # (x1, y1, x2, y2, track_id, confidence)

    def clear(self) -> None: ...             # drop all tracks; ids keep counting


class Embedder(Protocol):
    def extract(self, frame_bgr: np.ndarray, bboxes: Sequence[Box]) -> list[np.ndarray]: ...


class SpoofChecker(Protocol):
    def check_faces(self, frame_bgr: np.ndarray, face_bboxes: Sequence[Box],
                    ) -> dict[int, tuple[bool, float]]: ...   # index -> (is_spoof, score)


class DepthEstimator(Protocol):
    def estimate(self, rgb: np.ndarray, intrinsics: tuple[float, float, float, float],
                 canonical_to_real_scale: float) -> np.ndarray: ...   # metres, (H, W)


class PersonDetector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[tuple[float, float, float, float, float]]: ...


class LipReader(Protocol):
    def opening(self, frame_bgr: np.ndarray, box: Box) -> float | None: ...  # inner-lip gap / width


class ActiveSpeakerDetector(Protocol):
    def predict(self, pcm16: np.ndarray, crops: np.ndarray) -> np.ndarray: ...
    # pcm16: (16000,) int16 mono; crops: (25,112,112) uint8 grayscale face crops
    # -> (25,) float32 probabilities in [0, 1]

"""
Presentation Attack (Spoof) Detector — Pretrained PAD Model Ensemble.

Receives face bounding boxes from the face tracking thread (no internal
face detection). Runs MiniFASNetV2 + MiniFASNetV1SE ensemble on each
face crop to classify live human vs. presentation attack.

Architecture:
  Face bboxes (from SCRFD in Thread 1)
      ↓
  Face crop with bbox expansion (scale factor from model filename)
      ↓
  MiniFASNetV2  ──┐
                   ├── Ensemble (sum softmax probabilities)  →  Live / Spoof
  MiniFASNetV1SE ─┘

Class mapping (from original Silent-Face-Anti-Spoofing training):
  Class 0 — Fake (print attack)
  Class 1 — Real (live human)
  Class 2 — Fake (replay attack)

Important: the pretrained model expects BGR input in [0, 255] range (uint8 as
float32), NOT [0, 1].  The original repo uses a custom ToTensor that skips the
division by 255.

Interface:
  predict(face_image) → (is_live, confidence)    — pure PAD inference
  check_faces(frame_bgr, face_bboxes) → Dict[int, Tuple[bool, float]]
"""

from __future__ import annotations

import os
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import cv2
import numpy as np
import torch

from Visual.infrastructure.spoof.minifasnet_models import MiniFASNetV1SE, MiniFASNetV2


# ═══════════════════════════════════════════════════════════════════════
# Model registry — each entry maps a weight filename to its config
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class _PadModelSpec:
    """Configuration for one PAD model in the ensemble."""

    filename: str           # e.g. "2.7_80x80_MiniFASNetV2.pth"
    factory: type           # MiniFASNetV2 or MiniFASNetV1SE
    num_classes: int = 3
    conv6_kernel: Tuple[int, int] = (5, 5)  # ceil(80/16) = 5
    bbox_scale: float = 2.7                 # from filename


_PAD_MODELS = [
    _PadModelSpec(
        filename="2.7_80x80_MiniFASNetV2.pth",
        factory=MiniFASNetV2,
        num_classes=3,
        conv6_kernel=(5, 5),
        bbox_scale=2.7,
    ),
    _PadModelSpec(
        filename="4_0_0_80x80_MiniFASNetV1SE.pth",
        factory=MiniFASNetV1SE,
        num_classes=3,
        conv6_kernel=(5, 5),
        bbox_scale=4.0,
    ),
]

# Label 1 = real/live; labels 0 and 2 = fake/spoof
_LIVE_CLASS = 1


# ═══════════════════════════════════════════════════════════════════════
# SpoofDetector
# ═══════════════════════════════════════════════════════════════════════

class SpoofDetector:
    """
    Face anti-spoofing detector using an ensemble of pretrained PAD models.

    Does NOT perform face detection — receives face bounding boxes from
    the face tracking thread (Thread 1). Only runs MiniFASNet inference.

    Usage:
        det = SpoofDetector(device="cuda")
        det.prepare()                    # download/load PAD models

        # Pure PAD on a face crop
        is_live, confidence, replay = det.predict(face_crop_bgr)

        # Full spoof check for tracked faces
        results = det.check_faces(frame_bgr, face_bboxes)
        # → {0: (is_spoof, score), 1: (is_spoof, score), ...}
    """

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    _WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "pad_weights")

    def __init__(
        self,
        *,
        pad_models: List[_PadModelSpec] | None = None,
        pad_input_size: Tuple[int, int] = (80, 80),
        pad_live_threshold: float = 0.5,
        device: str = "cpu",
    ):
        """
        Args:
            pad_models: List of _PadModelSpec defining the ensemble.
                        Defaults to MiniFASNetV2 + MiniFASNetV1SE.
            pad_input_size: (H, W) input size for all PAD models.
            pad_live_threshold: Ensemble live score ≥ this → REAL.
            device: Torch device string ("cpu" or "cuda").
        """
        self._pad_specs = pad_models or _PAD_MODELS
        self._pad_input_size = pad_input_size
        self._pad_live_threshold = pad_live_threshold
        self._device = device

        self._pad_models: List[torch.nn.Module] = []
        self._prepared = False

    # ==================================================================
    # Lifecycle
    # ==================================================================

    def prepare(self) -> None:
        """Load all PAD models. Call once before inference."""
        if self._prepared:
            return

        # PAD models (ensemble)
        for spec in self._pad_specs:
            model = self._create_pad_model(spec)
            self._pad_models.append(model)

        self._prepared = True

    def _create_pad_model(self, spec: _PadModelSpec) -> torch.nn.Module:
        """Create one PAD model and load its pretrained weights."""
        model = spec.factory(
            num_classes=spec.num_classes,
            conv6_kernel=spec.conv6_kernel,
            img_channel=3,
        )

        weight_path = os.path.join(self._WEIGHTS_DIR, spec.filename)
        if not os.path.exists(weight_path):
            self._download_weight(spec.filename, weight_path)

        state_dict = torch.load(
            weight_path, map_location="cpu", weights_only=True,
        )
        # Handle DataParallel 'module.' prefix
        stripped = OrderedDict()
        for k, v in state_dict.items():
            stripped[k[7:] if k.startswith("module.") else k] = v

        model.load_state_dict(stripped, strict=True)
        model.to(self._device)
        model.eval()
        return model

    def _download_weight(self, filename: str, dest: str) -> None:
        """Download a PAD weight file from the official GitHub repo."""
        import urllib.request

        url = (
            "https://raw.githubusercontent.com/minivision-ai/"
            "Silent-Face-Anti-Spoofing/master/resources/"
            f"anti_spoof_models/{filename}"
        )
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print(f"[spoof] downloading {filename} …")
        urllib.request.urlretrieve(url, dest)
        print(f"[spoof] saved to {dest}")

    @property
    def is_prepared(self) -> bool:
        return self._prepared

    # ==================================================================
    # Core Interface — PAD inference on a single face crop
    # ==================================================================

    def predict(self, face_image: np.ndarray) -> Tuple[bool, float, float]:
        """
        Run PAD inference on a single face crop using the ensemble.

        The face image should be BGR (OpenCV default), uint8, any size.
        It will be resized to the PAD model's input size automatically.

        IMPORTANT: The model expects [0, 255] range (NOT [0, 1]) — the
        original repo's custom ToTensor skips the division by 255.

        Args:
            face_image: BGR face image (H, W, 3), uint8.

        Returns:
            (is_live, live_score, replay_score)
            - is_live: True if the face is classified as a live human.
            - live_score: Live-class (1) ensemble probability [0, 1].
            - replay_score: Replay-attack class (2) ensemble probability [0, 1].
                            High values indicate a phone/tablet/screen replay.
        """
        if not self._prepared:
            raise RuntimeError("Call prepare() before predict()")

        # Resize to model input size
        resized = cv2.resize(
            face_image,
            (self._pad_input_size[1], self._pad_input_size[0]),
            interpolation=cv2.INTER_LINEAR,
        )
        # Convert to tensor — NO division by 255 (model expects [0, 255] as float32)
        tensor = (
            torch.from_numpy(resized.transpose(2, 0, 1))
            .float()
            .unsqueeze_(0)
            .to(self._device)
        )

        # Ensemble: sum softmax probabilities from all models
        accumulated = None
        with torch.no_grad():
            for model in self._pad_models:
                logits = model(tensor)                        # (1, num_classes)
                probs = torch.softmax(logits, dim=1)          # (1, num_classes)
                if accumulated is None:
                    accumulated = probs
                else:
                    accumulated = accumulated + probs

        num_models = len(self._pad_models)
        # Class 1 = live; classes 0, 2 = spoof
        live_score = float(accumulated[0, _LIVE_CLASS].cpu()) / num_models
        replay_score = float(accumulated[0, 2].cpu()) / num_models  # explicit replay
        is_live = live_score >= self._pad_live_threshold
        return is_live, live_score, replay_score

    # ==================================================================
    # High-Level — full spoof check for tracked faces
    # ==================================================================

    def check_faces(
        self,
        frame_bgr: np.ndarray,
        face_bboxes: List[Tuple[float, float, float, float]],
    ) -> Dict[int, Tuple[bool, float]]:
        """
        Full spoof check for tracked faces.

        1. For each face bbox: expand → crop BGR region → PAD ensemble.
        2. Each face is independently classified as live or spoof.

        Args:
            frame_bgr: Full BGR frame (H, W, 3), uint8.
            face_bboxes: List of face bounding boxes (x1, y1, x2, y2).

        Returns:
            Dict mapping face_index → (is_spoof, confidence).
            is_spoof: True if the face appears to be a presentation attack.
            confidence: Spoof confidence score (1.0 - live_score).
        """
        if not self._prepared:
            raise RuntimeError("Call prepare() before check_faces()")

        fh, fw = frame_bgr.shape[:2]
        results: Dict[int, Tuple[bool, float]] = {}

        for idx, bbox in enumerate(face_bboxes):
            # Expand face bbox by the max scale factor from the ensemble
            max_scale = max(spec.bbox_scale for spec in self._pad_specs)
            expanded = self._expand_bbox(bbox, max_scale, fw, fh)

            ex1, ey1, ex2, ey2 = expanded
            if ex2 <= ex1 + 8 or ey2 <= ey1 + 8:
                results[idx] = (False, 0.0)  # face too small → assume real
                continue

            # Crop BGR (NOT RGB — model was trained with OpenCV BGR input)
            face_crop = frame_bgr[ey1:ey2, ex1:ex2]

            try:
                is_live, live_score, replay_score = self.predict(face_crop)
            except Exception:
                results[idx] = (False, 0.0)  # error → assume real (safe default)
                continue

            # Attack signals:
            #   attack_score = class_0 + class_2 = 1.0 - live_score
            #   replay_score = class_2 specifically (phone/tablet/screen)
            # Either signal alone can trigger a spoof verdict.
            attack_score = 1.0 - live_score
            spoof_conf = max(attack_score, replay_score)
            is_spoof = (attack_score >= self._pad_live_threshold) or (replay_score >= 0.40)
            results[idx] = (is_spoof, spoof_conf)

        return results

    # ==================================================================
    # Helpers
    # ==================================================================

    @staticmethod
    def _expand_bbox(
        bbox: Tuple[float, float, float, float],
        scale: float,
        frame_w: int,
        frame_h: int,
    ) -> Tuple[int, int, int, int]:
        """
        Expand a face bounding box by *scale* around its centre,
        clamped to frame bounds.

        Args:
            bbox: (x1, y1, x2, y2) in pixel coordinates.
            scale: Expansion factor (e.g. 2.7, 4.0).
            frame_w, frame_h: Frame dimensions.

        Returns:
            Expanded (x1, y1, x2, y2) as ints, clamped to [0, w-1] × [0, h-1].
        """
        x1, y1, x2, y2 = bbox
        bw, bh = x2 - x1, y2 - y1

        # Cap scale so expanded box stays within frame
        max_scale_w = (frame_w - 1) / max(bw, 1.0)
        max_scale_h = (frame_h - 1) / max(bh, 1.0)
        scale = min(scale, max_scale_w, max_scale_h)

        nw, nh = bw * scale, bh * scale
        cx, cy = x1 + bw / 2.0, y1 + bh / 2.0

        nx1 = int(cx - nw / 2.0)
        ny1 = int(cy - nh / 2.0)
        nx2 = int(cx + nw / 2.0)
        ny2 = int(cy + nh / 2.0)

        # Clamp
        nx1 = max(0, nx1)
        ny1 = max(0, ny1)
        nx2 = min(frame_w - 1, nx2)
        ny2 = min(frame_h - 1, ny2)

        return (nx1, ny1, nx2, ny2)

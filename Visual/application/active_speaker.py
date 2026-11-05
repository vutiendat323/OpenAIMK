"""Active speaker: the face crop Light-ASD reads, and the inference worker.

Crop a face box into the grayscale 112x112 input Light-ASD expects.

Matches the upstream Columbia_test.py geometry: pad the frame by 110 outside
its edges, crop [cx-1.4bs, cx+1.4bs] x [cy-bs, cy+1.8bs] around the box
(bs = half the larger of its width/height), resize to 224x224, then take the
center 112x112. Upstream crops in BGR and only converts to grayscale later
(reading the crop back from an intermediate video file) -- crop and resize
happen before grayscale, not after.
"""

from __future__ import annotations

import time

import cv2
import numpy as np

from Visual.application.ports import ActiveSpeakerDetector
from Visual.application.state import SharedState
from Visual.config import Config
from Visual.domain.active_speaker import NUM_BINS, PACKET_SECS, AsdResult

_CROP_SCALE = 0.40  # cs in Columbia_test.py
_PAD_VALUE = 110
_RESIZE = 224
_OUT = 112
_HALF = _OUT // 2


def prepare_face_crop(frame_bgr: np.ndarray, box: tuple) -> np.ndarray | None:
    x1, y1, x2, y2 = box[:4]
    w, h = x2 - x1, y2 - y1
    if w <= 0 or h <= 0:
        return None
    bs = max(w, h) / 2.0
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

    pad = int(bs * (1 + 2 * _CROP_SCALE))
    padded = cv2.copyMakeBorder(
        frame_bgr, pad, pad, pad, pad, cv2.BORDER_CONSTANT,
        value=(_PAD_VALUE, _PAD_VALUE, _PAD_VALUE),
    )
    mx, my = cx + pad, cy + pad
    y_lo, y_hi = int(my - bs), int(my + bs * (1 + 2 * _CROP_SCALE))
    x_lo, x_hi = int(mx - bs * (1 + _CROP_SCALE)), int(mx + bs * (1 + _CROP_SCALE))
    if y_hi <= y_lo or x_hi <= x_lo:
        return None
    h_p, w_p = padded.shape[:2]
    if y_lo < 0 or x_lo < 0 or y_hi > h_p or x_hi > w_p:
        return None

    crop = padded[y_lo:y_hi, x_lo:x_hi]
    if crop.size == 0:
        return None
    resized = cv2.resize(crop, (_RESIZE, _RESIZE))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    lo, hi = _RESIZE // 2 - _HALF, _RESIZE // 2 + _HALF
    return gray[lo:hi, lo:hi]


def _asd_loop(state: SharedState, cfg: Config, detector: ActiveSpeakerDetector) -> None:
    """Score the newest complete window of the selected track as soon as input arrives.

    Single worker: take one window, infer outside every lock, publish, then
    take the next -- never a queue, never a second window in flight (AVBuffer
    only accepts the result of the window it issued last, and a reset while
    inferring makes it refuse this one).  A model failure disables ASD for
    the process; face tracking and mouth activity carry on without it.
    """
    while state.running:
        # Woken by new audio or a crop; the timeout keeps a stalled input
        # from parking the worker for good.
        state.asd.wait_for_input(PACKET_SECS)
        window = state.asd.next_window(offset_secs=cfg.asd_audio_offset_secs, now=time.time())
        if window is None:
            continue
        try:
            probs = np.asarray(detector.predict(window.pcm16, window.crops), dtype=np.float32)
            if probs.shape != (NUM_BINS,) or not ((probs >= 0.0) & (probs <= 1.0)).all():
                raise ValueError(f"model output must be 25 values in [0, 1], got {probs.shape}")
        except Exception as e:
            print(f"[asd] inference failed, ASD disabled until restart: {e}")
            state.asd_status = "unavailable"
            state.asd.stop_stream(window.stream_id)
            return
        state.asd.publish(AsdResult(window.stream_id, window.track_id, window.audio_t0, probs))

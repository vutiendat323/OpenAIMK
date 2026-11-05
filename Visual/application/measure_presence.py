"""Measure presence: YOLO person boxes + Metric3D depth, on the same frame.

Answers "is a person standing there", face visible or not.  Handed the
models it runs -- it never builds them.
"""

import logging
import time

import cv2
import torch

from Visual.application.ports import DepthEstimator, PersonDetector
from Visual.application.state import SharedState
from Visual.config import Config
from Visual.domain.geometry import body_distance

_log = logging.getLogger(__name__)


def _presence_loop(state: SharedState, cfg: Config, depth_estimator: DepthEstimator,
                   person_detector: PersonDetector | None = None) -> None:
    """Every ``cfg.depth_interval_sec``, measure the distance to each person.

    Person boxes and the depth map come from the same frame by construction,
    so they cannot drift apart the way the old ROI/depth pairing did (a
    sideways walk read 1.7-2.0 m instead of 1.0 m).  *depth_estimator* has
    ``estimate(rgb, intrinsics, scale) -> depth map``; *person_detector*, when
    given, has ``detect(frame) -> [(x1, y1, x2, y2, conf)]``.
    """
    depth_stream = torch.cuda.Stream() if "cuda" in cfg.device else None

    while state.running:
        # Before the frame: a camera switch (Scene.reset) after this point
        # makes the tick's bodies stale, and Scene drops them.
        generation = state.scene.generation
        snap = state.frame_snapshot()
        frame = snap.frame
        if frame is None:
            time.sleep(0.02)
            continue

        t0 = time.perf_counter()
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # A remote camera's estimate replaces the C920 calibration, and the
        # canonical-to-real scale follows its focal length -- both taken with
        # the frame, so a switch cannot pair one camera's frame with the other's.
        intrinsics = snap.intrinsics
        if intrinsics is None:
            intrinsics, scale = cfg.intrinsics, cfg.canonical_to_real_scale
        else:
            scale = cfg.canonical_to_real_scale * intrinsics[0] / cfg.intrinsics[0]

        try:
            if depth_stream is not None:
                with torch.cuda.stream(depth_stream):
                    depth_map = depth_estimator.estimate(
                        frame_rgb, intrinsics, scale)
                depth_stream.synchronize()
            else:
                depth_map = depth_estimator.estimate(
                    frame_rgb, intrinsics, scale)

            bodies = []
            if person_detector is not None:
                for x1, y1, x2, y2, conf in person_detector.detect(frame):
                    z = body_distance(depth_map, (x1, y1, x2, y2),
                                      cfg.person_shrink, cfg.person_depth_percentile)
                    if z is not None:
                        bodies.append({"box": (x1, y1, x2, y2), "dist": z})

            dt = (time.perf_counter() - t0) * 1000.0
            state.scene.observe_bodies(bodies, generation=generation)
            state.set_timing("presence", dt)
            _log.debug("[presence] %.0f ms, bodies=%d", dt, len(bodies))
        except Exception as e:
            _log.error("[presence] error: %s", e)

        # Interval is a period, not a gap: a 600 ms inference inside a 1 s
        # interval sleeps 400 ms, so the rate matches the configured value
        # instead of drifting to interval + inference time.
        elapsed = time.perf_counter() - t0
        time.sleep(max(0.0, cfg.depth_interval_sec - elapsed))
